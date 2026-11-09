"""Sensors for delivery information and update timestamps."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import VolvoDeliveryConfigEntry
from .const import CONF_ORDER_NUMBER, DELIVERY_URL, DOMAIN
from .coordinator import VolvoDeliveryCoordinator


@dataclass(frozen=True, kw_only=True)
class VolvoSensorDescription(SensorEntityDescription):
    """Read one value from the shared coordinator."""

    value_fn: Callable[[VolvoDeliveryCoordinator], str | date | int | None]


def days_until_delivery(coordinator: VolvoDeliveryCoordinator) -> int | None:
    """Count calendar days using Home Assistant's configured timezone."""
    if coordinator.forecast is None or coordinator.last_checked is None:
        return None
    today = dt_util.as_local(coordinator.last_checked).date()
    return max(0, (coordinator.forecast.start - today).days)


SENSORS = (
    VolvoSensorDescription(
        key="delivery_start",
        translation_key="delivery_start",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.forecast.start if c.forecast else None,
    ),
    VolvoSensorDescription(
        key="delivery_end",
        translation_key="delivery_end",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda c: c.forecast.end if c.forecast else None,
    ),
    VolvoSensorDescription(
        key="days_until_delivery",
        translation_key="days_until_delivery",
        icon="mdi:calendar-start",
        native_unit_of_measurement="d",
        value_fn=days_until_delivery,
    ),
    VolvoSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:car-clock",
        value_fn=lambda c: c.data.status,
    ),
    VolvoSensorDescription(
        key="delivery_estimate",
        translation_key="delivery_estimate",
        icon="mdi:calendar-clock",
        value_fn=lambda c: c.data.delivery_estimate,
    ),
    VolvoSensorDescription(
        key="order_changes",
        translation_key="order_changes",
        icon="mdi:playlist-edit",
        value_fn=lambda c: c.data.order_changes,
    ),
    VolvoSensorDescription(
        key="last_changed",
        translation_key="last_changed",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.last_changed,
    ),
    VolvoSensorDescription(
        key="last_checked",
        translation_key="last_checked",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.last_checked,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoDeliveryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors using the first successful shared refresh."""
    async_add_entities(
        VolvoDeliverySensor(entry, description) for description in SENSORS
    )


class VolvoDeliverySensor(CoordinatorEntity[VolvoDeliveryCoordinator], SensorEntity):
    """One sensor per delivery field."""

    _attr_has_entity_name = True
    entity_description: VolvoSensorDescription

    def __init__(
        self, entry: VolvoDeliveryConfigEntry, description: VolvoSensorDescription
    ) -> None:
        super().__init__(entry.runtime_data)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ORDER_NUMBER]}_{description.key}"
        self._tracking_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ORDER_NUMBER])},
            name=entry.title,
            manufacturer="Volvo Cars",
            model=self.coordinator.data.model,
            configuration_url=DELIVERY_URL,
        )

    @property
    def native_value(self) -> str | date | int | None:
        """Return the full text in attributes if it exceeds HA's state limit."""
        value = self.entity_description.value_fn(self.coordinator)
        return value[:255] if isinstance(value, str) else value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful context without personal sales contact information."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {
            "delivery_tracking_id": self._tracking_id,
            "delivery_field": self.entity_description.key,
        }
        match self.entity_description.key:
            case "status":
                attributes.update(
                    {
                        "full_text": data.status,
                        "previous_status": self.coordinator.previous_status,
                        "model": data.model,
                        "specification": data.specification,
                        "image_url": data.image_url,
                        "image_alt": data.image_alt,
                        "rear_image_url": data.rear_image_url,
                        "interior_image_url": data.interior_image_url,
                        "model_url": data.model_url,
                        "manual_url": data.manual_url,
                    }
                )
            case "delivery_estimate":
                attributes.update(
                    {
                        "full_text": data.delivery_estimate,
                        "title": data.delivery_estimate_title,
                    }
                )
            case "order_changes":
                attributes.update(
                    {
                        "full_text": data.order_changes,
                        "description": data.order_changes_description,
                    }
                )
        if self.entity_description.key in (
            "delivery_estimate",
            "delivery_start",
            "delivery_end",
            "days_until_delivery",
        ):
            forecast = self.coordinator.forecast
            attributes.update(
                {
                    "estimated_start": forecast.start.isoformat() if forecast else None,
                    "estimated_end": forecast.end.isoformat() if forecast else None,
                    "delivery_week": forecast.week if forecast else None,
                    "delivery_year": forecast.year if forecast else None,
                    "year_source": forecast.year_source if forecast else None,
                    "is_estimate": True,
                }
            )
        return attributes
