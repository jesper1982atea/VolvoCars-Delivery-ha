"""Test daily polling and persistent change detection with real HA helpers."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.volvo_delivery.api import (
    VolvoDeliveryAuthError,
    VolvoDeliveryError,
    parse_delivery,
)
from custom_components.volvo_delivery.coordinator import VolvoDeliveryCoordinator


def make_coordinator(hass, data):
    entry = SimpleNamespace(
        entry_id="fictional-entry",
        async_on_unload=MagicMock(),
        pref_disable_polling=False,
    )
    client = SimpleNamespace(async_get_delivery=AsyncMock(return_value=data))
    return VolvoDeliveryCoordinator(hass, entry, client)


async def test_daily_interval(hass, payload):
    coordinator = make_coordinator(hass, parse_delivery(payload, "1234567"))
    assert coordinator.update_interval == timedelta(hours=24)


async def test_subscribing_schedules_one_daily_poll(hass, payload):
    coordinator = make_coordinator(hass, parse_delivery(payload, "1234567"))
    before = hass.loop.time()
    remove_first = coordinator.async_add_listener(lambda: None)
    scheduled = coordinator._unsub_refresh.__self__
    assert 86399 <= scheduled.when() - before <= 86401
    remove_second = coordinator.async_add_listener(lambda: None)
    assert coordinator._unsub_refresh.__self__ is scheduled
    remove_first()
    assert not scheduled.cancelled()
    remove_second()
    assert scheduled.cancelled()


async def test_first_poll_unchanged_change_and_restart(hass, payload):
    original = parse_delivery(payload, "1234567")
    coordinator = make_coordinator(hass, original)
    start = dt_util.utcnow()
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=start,
    ):
        await coordinator.async_load()
        assert await coordinator._async_update_data() == original
    assert coordinator.last_changed == start
    assert coordinator.previous_status is None

    tomorrow = start + timedelta(days=1)
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=tomorrow,
    ):
        await coordinator._async_update_data()
    assert coordinator.last_checked == tomorrow
    assert coordinator.last_changed == start

    changed = replace(original, status="In transit")
    coordinator.client.async_get_delivery.return_value = changed
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=tomorrow,
    ):
        await coordinator._async_update_data()
    assert coordinator.last_changed == tomorrow
    assert coordinator.previous_status == "Order placed"

    restarted = make_coordinator(hass, changed)
    await restarted.async_load()
    await restarted._async_update_data()
    assert restarted.last_changed == tomorrow
    assert restarted.previous_status == "Order placed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("delivery_estimate", "Delivery expected in week 6"),
        ("delivery_estimate_title", "11 weeks remaining"),
        ("order_changes", None),
        ("order_changes_description", "Updated information"),
        ("model", "EX90"),
        ("specification", "Another specification"),
        ("image_url", "https://wizz.volvocars.com/images/updated-example.png"),
    ],
)
async def test_non_status_changes_are_tracked(hass, payload, field, value):
    original = parse_delivery(payload, "1234567")
    coordinator = make_coordinator(hass, original)
    await coordinator._async_update_data()
    old_changed = coordinator.last_changed
    coordinator.client.async_get_delivery.return_value = replace(
        original, **{field: value}
    )
    await coordinator._async_update_data()
    assert coordinator.last_changed > old_changed
    assert coordinator.previous_status == original.status


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (VolvoDeliveryAuthError("Authorization rejected"), ConfigEntryAuthFailed),
        (VolvoDeliveryError("Unavailable"), UpdateFailed),
    ],
)
async def test_failed_fetch_does_not_change_baseline(hass, payload, error, expected):
    coordinator = make_coordinator(hass, parse_delivery(payload, "1234567"))
    await coordinator._async_update_data()
    last_checked = coordinator.last_checked
    last_changed = coordinator.last_changed
    snapshot = coordinator._snapshot.copy()
    coordinator.client.async_get_delivery.side_effect = error
    with pytest.raises(expected):
        await coordinator._async_update_data()
    assert coordinator.last_checked == last_checked
    assert coordinator.last_changed == last_changed
    assert coordinator._snapshot == snapshot


async def test_changed_while_stopped(hass, payload):
    original = parse_delivery(payload, "1234567")
    first = make_coordinator(hass, original)
    await first._async_update_data()
    restarted = make_coordinator(hass, replace(original, status="Delivered"))
    await restarted.async_load()
    await restarted._async_update_data()
    assert restarted.previous_status == original.status
    assert restarted.last_changed > first.last_changed


async def test_forecast_year_does_not_roll_when_old_week_passes(hass, payload):
    data = replace(
        parse_delivery(payload, "1234567"),
        delivery_estimate="Leverans v. 5",
        delivery_estimate_title="12 veckor kvar till beräknad leverans",
    )
    coordinator = make_coordinator(hass, data)
    first = dt_util.parse_datetime("2026-11-09T12:00:00+00:00")
    much_later = dt_util.parse_datetime("2027-11-09T12:00:00+00:00")
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=first,
    ):
        await coordinator._async_update_data()
    start = coordinator.forecast.start
    restarted = make_coordinator(hass, replace(data, status="Status updated"))
    await restarted.async_load()
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=much_later,
    ):
        await restarted._async_update_data()
    assert restarted.forecast.start == start
    assert restarted.forecast.year == 2027


async def test_updated_estimate_gets_new_reference(hass, payload):
    data = replace(
        parse_delivery(payload, "1234567"),
        delivery_estimate="Leverans v. 5",
        delivery_estimate_title="12 veckor kvar till beräknad leverans",
    )
    coordinator = make_coordinator(hass, data)
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=dt_util.parse_datetime("2026-11-09T12:00:00+00:00"),
    ):
        await coordinator._async_update_data()
    assert coordinator.forecast.week == 5
    coordinator.client.async_get_delivery.return_value = replace(
        data, delivery_estimate="Leverans v. 6"
    )
    with patch(
        "custom_components.volvo_delivery.coordinator.dt_util.utcnow",
        return_value=dt_util.parse_datetime("2026-11-16T12:00:00+00:00"),
    ):
        await coordinator._async_update_data()
    assert coordinator.forecast.week == 6
    assert coordinator.forecast.start.isoformat() == "2027-02-08"
