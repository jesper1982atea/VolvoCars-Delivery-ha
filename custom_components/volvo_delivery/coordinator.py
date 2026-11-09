"""Daily polling and persistent delivery change detection."""

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
            self._snapshot[key] != snapshot[key]
            for key in ("delivery_estimate", "delivery_estimate_title")
        )
        reference = now if estimate_changed else (self._estimate_reference or now)
        if self._snapshot != snapshot:
            # The first result establishes a baseline, not a delivery change.
            previous_status = (
                self._snapshot["status"] if self._snapshot is not None else None
            )
            await self._store.async_save(
                {
                    "snapshot": snapshot,
                    "previous_status": previous_status,
                    "last_changed": now.isoformat(),
                    "estimate_reference": reference.isoformat(),
                }
            )
            self.previous_status = previous_status
            self.last_changed = now
            self._snapshot = snapshot
        self._estimate_reference = reference
        self.forecast = delivery_forecast(data, dt_util.as_local(reference).date())
        self.last_checked = now
        return data
