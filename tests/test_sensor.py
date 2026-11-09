"""Test sensor values, metadata and shared polling."""

from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace

from custom_components.volvo_delivery.api import parse_delivery
from custom_components.volvo_delivery.forecast import DeliveryForecast
from custom_components.volvo_delivery.sensor import SENSORS, VolvoDeliverySensor


def make_sensor(payload, key):
    coordinator = SimpleNamespace(
        data=parse_delivery(payload, "1234567"),
        previous_status="Previous status",
        last_changed=None,
        last_checked=None,
        forecast=None,
    )
    entry = SimpleNamespace(
        runtime_data=coordinator,
        data={"order_number": "1234567"},
        title="Volvo 1234567",
        entry_id="test-tracking-id",
    )
    description = next(item for item in SENSORS if item.key == key)
    return VolvoDeliverySensor(entry, description)


def test_status_sensor(payload):
    sensor = make_sensor(payload, "status")
    assert sensor.native_value == "Order placed"
    assert sensor.unique_id == "1234567_status"
    assert sensor.extra_state_attributes["previous_status"] == "Previous status"
    assert "contact" not in sensor.extra_state_attributes


def test_long_text_has_safe_state_and_full_attribute(payload):
    sensor = make_sensor(payload, "status")
    sensor.coordinator.data = replace(sensor.coordinator.data, status="x" * 300)
    assert len(sensor.native_value) == 255
    assert sensor.extra_state_attributes["full_text"] == "x" * 300


def test_estimate_not_guessed_as_date(payload):
    sensor = make_sensor(payload, "delivery_estimate")
    assert sensor.native_value == "Delivery expected in week 5"
    assert sensor.extra_state_attributes["title"] == "12 weeks remaining"


def test_optional_empty_sensor(payload):
    payload["changeOrder"] = None
    sensor = make_sensor(payload, "order_changes")
    assert sensor.native_value is None


def test_card_can_discover_renamed_entities_by_tracking_id(payload):
    sensor = make_sensor(payload, "status")
    assert sensor.extra_state_attributes["delivery_tracking_id"] == "test-tracking-id"
    assert sensor.extra_state_attributes["delivery_field"] == "status"


def test_vehicle_configuration_and_media_available_to_card(payload):
    payload["car"].update(
        {
            "infoImg": "https://wizz.volvocars.com/images/example.png",
            "altText": "Example Volvo",
            "getToKnowImg": "https://wizz.volvocars.com/images/rear.png",
            "manualImg": "https://wizz.volvocars.com/images/interior.png",
            "infoHref": "https://www.volvocars.com/se/cars/ex60-electric",
            "manualHref": "https://www.volvocars.com/se/support/car/ex60",
        }
    )
    attributes = make_sensor(payload, "status").extra_state_attributes
    assert attributes["image_url"] == payload["car"]["infoImg"]
    assert attributes["image_alt"] == "Example Volvo"
    assert attributes["rear_image_url"] == payload["car"]["getToKnowImg"]
    assert attributes["interior_image_url"] == payload["car"]["manualImg"]
    assert attributes["model_url"] == payload["car"]["infoHref"]
    assert attributes["manual_url"] == payload["car"]["manualHref"]
    assert attributes["specification"] == payload["car"]["carSpecificationString"]
    assert "contact" not in attributes


def test_forecast_sensors_and_attributes(payload):
    for key, expected in (
        ("delivery_start", date(2027, 2, 1)),
        ("delivery_end", date(2027, 2, 7)),
        ("days_until_delivery", 84),
    ):
        sensor = make_sensor(payload, key)
        sensor.coordinator.forecast = DeliveryForecast(
            date(2027, 2, 1), date(2027, 2, 7), 5, 2027, "inferred"
        )
        sensor.coordinator.last_checked = datetime(2026, 11, 9, 12, tzinfo=UTC)
        assert sensor.native_value == expected
        attributes = sensor.extra_state_attributes
        assert attributes["estimated_start"] == "2027-02-01"
        assert attributes["estimated_end"] == "2027-02-07"
        assert attributes["is_estimate"] is True
        assert attributes["year_source"] == "inferred"


def test_no_forecast_has_no_countdown(payload):
    assert make_sensor(payload, "days_until_delivery").native_value is None


def test_passed_week_has_zero_not_negative_countdown(payload):
    sensor = make_sensor(payload, "days_until_delivery")
    sensor.coordinator.forecast = DeliveryForecast(
        date(2027, 2, 1), date(2027, 2, 7), 5, 2027, "volvo"
    )
    sensor.coordinator.last_checked = datetime(2027, 2, 8, 12, tzinfo=UTC)
    assert sensor.native_value == 0
