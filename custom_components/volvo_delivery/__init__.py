"""Volvo delivery tracking integration."""

from pathlib import Path

from homeassistant.components import frontend as ha_frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import VolvoDeliveryClient
from .const import CARD_URL, CONF_AUTHORIZATION, CONF_ORDER_NUMBER, DOMAIN
from .coordinator import VolvoDeliveryCoordinator

type VolvoDeliveryConfigEntry = ConfigEntry[VolvoDeliveryCoordinator]

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Load the bundled dashboard card with the HACS integration."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/volvo_delivery/volvo-delivery-card.js",
                str(Path(__file__).parent / "frontend" / "volvo-delivery-card.js"),
                cache_headers=False,
            )
        ]
    )
    ha_frontend.add_extra_js_url(hass, CARD_URL)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: VolvoDeliveryConfigEntry
) -> bool:
    """Validate the order and set up daily updates."""
    coordinator = VolvoDeliveryCoordinator(
        hass,
        entry,
        VolvoDeliveryClient(
            async_get_clientsession(hass),
            entry.data[CONF_ORDER_NUMBER],
            entry.data[CONF_AUTHORIZATION],
        ),
    )
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VolvoDeliveryConfigEntry
) -> bool:
    """Unload the sensors and their polling subscription."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete locally stored tracking data."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
