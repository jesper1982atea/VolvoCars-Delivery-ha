"""Daily polling and persistent delivery change detection."""

import json
import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    DeliveryData,
    VolvoDeliveryAuthError,
    VolvoDeliveryClient,
    VolvoDeliveryError,
)
from .const import DOMAIN, UPDATE_INTERVAL
from .forecast import DeliveryForecast, delivery_forecast

LOGGER = logging.getLogger(__name__)

HISTORY_LIMIT = 10
HISTORY_TEXT_LIMIT = 100
HISTORY_BYTES_LIMIT = 9000


def history_text(value: str | None) -> str | None:
    """Keep attributes small enough for Home Assistant's state recorder."""
    if value is None:
        return value
    text = value[:HISTORY_TEXT_LIMIT]
    while len(json.dumps(text, ensure_ascii=True)) > 200:
        text = text[:-1]
    return text if text == value else text[:-1] + "…"


class VolvoDeliveryCoordinator(DataUpdateCoordinator[DeliveryData]):
    """Keep the previous successful snapshot across Home Assistant restarts."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: VolvoDeliveryClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.last_checked: datetime | None = None
        self.last_changed: datetime | None = None
        self.previous_status: str | None = None
        self.forecast: DeliveryForecast | None = None
        self._estimate_reference: datetime | None = None
        self._snapshot: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.history_started: datetime | None = None
        self.history_total = 0
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}"
        )

    async def async_load(self) -> None:
        """Load the baseline before the first network refresh."""
        if stored := await self._store.async_load():
            self._snapshot = stored["snapshot"]
            self.previous_status = stored["previous_status"]
            self.last_changed = dt_util.parse_datetime(stored["last_changed"])
            self._estimate_reference = dt_util.parse_datetime(
                stored.get("estimate_reference", stored["last_changed"])
            )
            self.history = stored.get("history", [])
            self.history_started = (
                dt_util.parse_datetime(stored["history_started"])
                if stored.get("history_started")
                else None
            )
            self.history_total = stored.get("history_total", 0)

    async def _async_update_data(self) -> DeliveryData:
        try:
            data = await self.client.async_get_delivery()
        except VolvoDeliveryAuthError as err:
            raise ConfigEntryAuthFailed("Volvo authorization rejected") from err
        except VolvoDeliveryError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        snapshot = data.as_dict()
        estimate_changed = self._snapshot is None or any(
            self._snapshot.get(key) != snapshot[key]
            for key in ("delivery_estimate", "delivery_estimate_title")
        )
        reference = now if estimate_changed else (self._estimate_reference or now)
        forecast = delivery_forecast(data, dt_util.as_local(reference).date())
        history = list(self.history)
        history_started = self.history_started
        history_total = self.history_total
        if history_started is None:
            history_started = now
            baseline_snapshot = self._snapshot or snapshot
            baseline_reference = self._estimate_reference or reference
            baseline_data = DeliveryData(
                **{
                    key: value
                    for key, value in baseline_snapshot.items()
                    if key in DeliveryData.__dataclass_fields__
                }
            )
            baseline_forecast = delivery_forecast(
                baseline_data, dt_util.as_local(baseline_reference).date()
            )
            history.append(
                {
                    "at": now.isoformat(),
                    "baseline": True,
                    "status": history_text(baseline_data.status),
                    "forecast_text": history_text(baseline_data.delivery_estimate),
                    "forecast_start": (
                        baseline_forecast.start.isoformat()
                        if baseline_forecast
                        else None
                    ),
                    "changes": [],
                }
            )
        if self._snapshot is not None:
            changes = []
            for key, label in (
                ("status", "status"),
                ("delivery_estimate", "forecast"),
                ("order_changes", "order"),
                ("order_changes_description", "order_description"),
                ("specification", "specification"),
                ("model", "model"),
            ):
                before, after = self._snapshot.get(key), snapshot.get(key)
                if before != after:
                    changes.append(
                        {
                            "field": label,
                            "before": history_text(before),
                            "after": history_text(after),
                        }
                    )
            previous_data = DeliveryData(
                **{
                    key: value
                    for key, value in self._snapshot.items()
                    if key in DeliveryData.__dataclass_fields__
                }
            )
            previous_forecast = delivery_forecast(
                previous_data,
                dt_util.as_local(self._estimate_reference or reference).date(),
            )
            previous_start = (
                previous_forecast.start.isoformat() if previous_forecast else None
            )
            current_start = forecast.start.isoformat() if forecast else None
            if previous_start != current_start and not any(
                item["field"] == "forecast" for item in changes
            ):
                changes.append(
                    {
                        "field": "forecast_date",
                        "before": previous_start,
                        "after": current_start,
                    }
                )
            media_keys = (
                "image_url",
                "image_alt",
                "rear_image_url",
                "interior_image_url",
                "model_url",
                "manual_url",
            )
            if any(
                key in self._snapshot and self._snapshot[key] != snapshot[key]
                for key in media_keys
            ):
                changes.append(
                    {
                        "field": "media",
                        "before": "Tidigare bilder eller länkar",
                        "after": "Uppdaterade bilder eller länkar",
                    }
                )
            if changes:
                history_total += 1
                history.append(
                    {
                        "at": now.isoformat(),
                        "baseline": False,
                        "status": history_text(data.status),
                        "forecast_text": history_text(data.delivery_estimate),
                        "forecast_start": current_start,
                        "changes": changes,
                    }
                )
                history = history[-HISTORY_LIMIT:]
                while (
                    len(history) > 1
                    and len(json.dumps(history, ensure_ascii=True))
                    > HISTORY_BYTES_LIMIT
                ):
                    history.pop(0)
        snapshot_changed = self._snapshot != snapshot
        if snapshot_changed or self.history_started is None:
            # The first result establishes a baseline, not a delivery change.
            previous_status = (
                self._snapshot["status"]
                if snapshot_changed and self._snapshot is not None
                else self.previous_status
            )
            last_changed = now if snapshot_changed else self.last_changed
            await self._store.async_save(
                {
                    "snapshot": snapshot,
                    "previous_status": previous_status,
                    "last_changed": last_changed.isoformat(),
                    "estimate_reference": reference.isoformat(),
                    "history": history,
                    "history_started": history_started.isoformat(),
                    "history_total": history_total,
                }
            )
            self.previous_status = previous_status
            self.last_changed = last_changed
            self._snapshot = snapshot
        self.history = history
        self.history_started = history_started
        self.history_total = history_total
        self._estimate_reference = reference
        self.forecast = forecast
        self.last_checked = now
        return data
