"""UI configuration and reauthentication for delivery tracking."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    VolvoDeliveryAuthError,
    VolvoDeliveryClient,
    VolvoDeliveryError,
    VolvoDeliveryOrderNotFound,
    normalize_authorization,
    valid_order_number,
)
from .const import CONF_AUTHORIZATION, CONF_ORDER_NUMBER, DOMAIN

LOGGER = logging.getLogger(__name__)

AUTH_FIELD = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


class VolvoDeliveryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one Swedish Volvo order."""

    VERSION = 1

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        if not valid_order_number(data[CONF_ORDER_NUMBER]):
            return {CONF_ORDER_NUMBER: "invalid_order"}
        try:
            data[CONF_AUTHORIZATION] = normalize_authorization(data[CONF_AUTHORIZATION])
        except ValueError:
            return {CONF_AUTHORIZATION: "invalid_auth"}
        client = VolvoDeliveryClient(
            async_get_clientsession(self.hass),
            data[CONF_ORDER_NUMBER],
            data[CONF_AUTHORIZATION],
        )
        try:
            await client.async_get_delivery()
        except VolvoDeliveryAuthError:
            return {"base": "invalid_auth"}
        except VolvoDeliveryOrderNotFound:
            return {"base": "order_not_found"}
        except VolvoDeliveryError as err:
            LOGGER.warning("Could not validate Volvo delivery: %s", err)
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate credentials before adding an order."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_ORDER_NUMBER] = user_input[CONF_ORDER_NUMBER].strip()
            await self.async_set_unique_id(user_input[CONF_ORDER_NUMBER])
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"Volvo {user_input[CONF_ORDER_NUMBER]}", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORDER_NUMBER): str,
                    vol.Required(CONF_AUTHORIZATION): AUTH_FIELD,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Request a replacement authorization value after HTTP 401/403."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace only the token, retaining the order and history."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            errors = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_AUTHORIZATION: data[CONF_AUTHORIZATION]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_AUTHORIZATION): AUTH_FIELD}),
            errors=errors,
        )
