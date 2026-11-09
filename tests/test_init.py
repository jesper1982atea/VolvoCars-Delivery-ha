"""Verify setup, failed startup, unloading and removal."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from custom_components.volvo_delivery import (
    async_remove_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.volvo_delivery.api import VolvoDeliveryError, parse_delivery
from custom_components.volvo_delivery.const import CARD_URL, DOMAIN


def make_entry():
    return SimpleNamespace(
        entry_id="test-lifecycle",
        title="Volvo example",
        data={"order_number": "1234567", "authorization": "example-token"},
        async_on_unload=MagicMock(),
        pref_disable_polling=False,
        state=ConfigEntryState.SETUP_IN_PROGRESS,
    )


async def test_setup_unload_and_delete(hass, payload):
    entry = make_entry()
    data = parse_delivery(payload, "1234567")
    with (
        patch("custom_components.volvo_delivery.async_get_clientsession"),
        patch(
            "custom_components.volvo_delivery.api.VolvoDeliveryClient.async_get_delivery",
            new_callable=AsyncMock,
            return_value=data,
        ) as fetch,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload,
    ):
        assert await async_setup_entry(hass, entry)
        assert entry.runtime_data.data == data
        fetch.assert_awaited_once()
        forward.assert_awaited_once_with(entry, ["sensor"])
        assert await async_unload_entry(hass, entry)
        unload.assert_awaited_once_with(entry, ["sensor"])
    store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
    assert await store.async_load() is not None
    await async_remove_entry(hass, entry)
    assert await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_load() is None


async def test_failed_first_refresh_is_not_success(hass):
    entry = make_entry()
    with (
        patch("custom_components.volvo_delivery.async_get_clientsession"),
        patch(
            "custom_components.volvo_delivery.api.VolvoDeliveryClient.async_get_delivery",
            new_callable=AsyncMock,
            side_effect=VolvoDeliveryError("Unavailable"),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
        forward.assert_not_awaited()


async def test_bundled_card_registered_without_lovelace_resource_edit(hass):
    from pathlib import Path

    hass.http = SimpleNamespace(async_register_static_paths=AsyncMock())
    with patch("custom_components.volvo_delivery.ha_frontend.add_extra_js_url") as add:
        assert await async_setup(hass, {})
    add.assert_called_once_with(hass, CARD_URL)
    paths = hass.http.async_register_static_paths.call_args.args[0]
    assert len(paths) == 1
    assert paths[0].url_path == CARD_URL.split("?")[0]
    assert Path(paths[0].path).is_file()
    assert paths[0].cache_headers is False
