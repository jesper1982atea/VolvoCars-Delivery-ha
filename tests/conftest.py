"""Fixtures containing only fictional delivery details."""

import asyncio

import pytest
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant


@pytest.fixture
def payload():
    return {
        "orderNumber": 1234567,
        "status": {"title": "Status", "copy": "Order placed"},
        "deliveryDateEstimate": {
            "title": "12 weeks remaining",
            "copy": "Delivery expected in week 5",
        },
        "changeOrder": {
            "title": "Changes allowed until 2027-01-01",
            "copy": "Contact your retailer",
        },
        "car": {
            "modelDescription": "EX60",
            "carSpecificationString": "EX60 example specification",
        },
        "contact": {"email": "not-retained@example.invalid"},
    }


@pytest.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    yield hass
    await hass.async_stop()
    await asyncio.sleep(0)
