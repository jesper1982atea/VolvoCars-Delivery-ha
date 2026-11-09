"""Test configuration validation without using actual credentials."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.volvo_delivery.api import (
    VolvoDeliveryAuthError,
    VolvoDeliveryError,
    VolvoDeliveryOrderNotFound,
)
from custom_components.volvo_delivery.config_flow import VolvoDeliveryConfigFlow


@pytest.mark.parametrize(
    ("order", "auth", "expected"),
    [
        ("123", "example-token", {"order_number": "invalid_order"}),
        ("1234567", "", {"authorization": "invalid_auth"}),
        ("1234567", "a\nb", {"authorization": "invalid_auth"}),
    ],
)
async def test_invalid_input_never_calls_api(hass, order, auth, expected):
    flow = VolvoDeliveryConfigFlow()
    flow.hass = hass
    with patch(
        "custom_components.volvo_delivery.config_flow.VolvoDeliveryClient"
    ) as client:
        assert (
            await flow._async_validate({"order_number": order, "authorization": auth})
            == expected
        )
    client.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, {}),
        (VolvoDeliveryAuthError(), {"base": "invalid_auth"}),
        (VolvoDeliveryOrderNotFound(), {"base": "order_not_found"}),
        (VolvoDeliveryError("Service unavailable"), {"base": "cannot_connect"}),
    ],
)
async def test_validation_maps_errors(hass, error, expected):
    flow = VolvoDeliveryConfigFlow()
    flow.hass = hass
    data = {"order_number": "1234567", "authorization": "example-token"}
    with (
        patch(
            "custom_components.volvo_delivery.config_flow.VolvoDeliveryClient"
        ) as client,
        patch("custom_components.volvo_delivery.config_flow.async_get_clientsession"),
    ):
        client.return_value.async_get_delivery = AsyncMock(side_effect=error)
        assert await flow._async_validate(data) == expected
    assert data["authorization"] == "Bearer example-token"


async def test_user_creates_entry(hass):
    flow = VolvoDeliveryConfigFlow()
    flow.hass = hass
    with (
        patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_async_validate", return_value={}),
    ):
        result = await flow.async_step_user(
            {"order_number": " 1234567 ", "authorization": "example-token"}
        )
    assert result["type"] == "create_entry"
    assert result["data"]["order_number"] == "1234567"


async def test_reauth_updates_only_authorization(hass):
    from types import SimpleNamespace

    flow = VolvoDeliveryConfigFlow()
    flow.hass = hass
    entry = SimpleNamespace(
        data={"order_number": "1234567", "authorization": "old-token"}
    )
    with (
        patch.object(flow, "_get_reauth_entry", return_value=entry),
        patch.object(flow, "_async_validate", return_value={}),
        patch.object(flow, "async_update_reload_and_abort") as update,
    ):
        await flow.async_step_reauth_confirm({"authorization": "new-token"})
    update.assert_called_once_with(entry, data_updates={"authorization": "new-token"})
