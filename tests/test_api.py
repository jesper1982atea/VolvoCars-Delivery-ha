"""Test response parsing, HTTP handling and secret-safe failures."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientConnectionError

from custom_components.volvo_delivery.api import (
    VolvoDeliveryAuthError,
    VolvoDeliveryClient,
    VolvoDeliveryError,
    VolvoDeliveryOrderNotFound,
    normalize_authorization,
    parse_delivery,
    valid_order_number,
)


@pytest.mark.parametrize("value", ["1234567", "12345678", "0123456"])
def test_valid_order(value):
    assert valid_order_number(value)


@pytest.mark.parametrize(
    "value", ["", "123456", "123456789", "../1234567", "１２３４５６７", "1234567\n"]
)
def test_invalid_order(value):
    assert not valid_order_number(value)


@pytest.mark.parametrize(
    "value", ["example-token", "Bearer example-token", " bearer example-token "]
)
def test_normalize_authorization(value):
    assert normalize_authorization(value) == "Bearer example-token"


@pytest.mark.parametrize("value", ["", "Bearer ", "a\nb", "a\rb", "a b"])
def test_reject_invalid_authorization(value):
    with pytest.raises(ValueError):
        normalize_authorization(value)


def test_parse_actual_page_structure(payload):
    data = parse_delivery(payload, "1234567")
    assert data.status == "Order placed"
    assert data.delivery_estimate == "Delivery expected in week 5"
    assert data.delivery_estimate_title == "12 weeks remaining"
    assert data.order_changes == "Changes allowed until 2027-01-01"
    assert data.model == "EX60"
    assert "contact" not in data.as_dict()
    assert "example.invalid" not in str(data.as_dict())


def test_missing_optional_data(payload):
    for key in ("deliveryDateEstimate", "changeOrder", "car", "contact"):
        payload.pop(key)
    data = parse_delivery(payload, "1234567")
    assert data.delivery_estimate is None
    assert data.order_changes is None
    assert data.model is None
    assert data.image_url is None
    assert data.model_url is None


def test_vehicle_media_and_configuration_from_volvo(payload):
    payload["car"].update(
        {
            "infoImg": "https://wizz.volvocars.com/images/example.png?w=600",
            "altText": "Volvo example model",
            "getToKnowImg": "https://wizz.volvocars.com/images/rear-example.png",
            "manualImg": "https://wizz.volvocars.com/images/interior-example.png",
            "infoHref": "https://www.volvocars.com/se/cars/ex60-electric",
            "manualHref": "https://www.volvocars.com/se/support/car/ex60",
        }
    )
    data = parse_delivery(payload, "1234567")
    assert data.specification == payload["car"]["carSpecificationString"]
    assert data.image_url == payload["car"]["infoImg"]
    assert data.image_alt == "Volvo example model"
    assert data.rear_image_url == payload["car"]["getToKnowImg"]
    assert data.interior_image_url == payload["car"]["manualImg"]
    assert data.model_url == payload["car"]["infoHref"]
    assert data.manual_url == payload["car"]["manualHref"]


@pytest.mark.parametrize(
    "url",
    [
        "http://wizz.volvocars.com/image.png",
        "https://example.invalid/image.png",
        "https://wizz.volvocars.com.example.invalid/image.png",
        "javascript:alert(1)",
        "data:image/svg+xml,test",
        "https://user:password@wizz.volvocars.com/image.png",
        "https://wizz.volvocars.com:8080/image.png",
        "https://wizz.volvocars.com:bad/image.png",
        "https://[invalid/image.png",
        "//wizz.volvocars.com/image.png",
    ],
)
def test_unexpected_image_url_rejected_without_leaking_value(payload, url):
    payload["car"]["infoImg"] = url
    with pytest.raises(VolvoDeliveryError) as raised:
        parse_delivery(payload, "1234567")
    assert url not in str(raised.value)


@pytest.mark.parametrize("value", [None, "", " "])
def test_empty_image_url_is_optional(payload, value):
    payload["car"]["infoImg"] = value
    assert parse_delivery(payload, "1234567").image_url is None


def test_model_link_must_be_volvo_page(payload):
    payload["car"]["infoHref"] = "https://wizz.volvocars.com/not-a-model-page"
    with pytest.raises(VolvoDeliveryError):
        parse_delivery(payload, "1234567")


def test_numeric_order_preserves_leading_zero_input(payload):
    payload["orderNumber"] = 123456
    assert parse_delivery(payload, "0123456").status == "Order placed"


@pytest.mark.parametrize(
    "patch",
    [
        {"orderNumber": 7654321},
        {"status": None},
        {"status": {"copy": " "}},
        {"status": {"copy": 1}},
        {"car": []},
        {"deliveryDateEstimate": "unexpected"},
    ],
)
def test_malformed_data(payload, patch):
    payload.update(patch)
    with pytest.raises(VolvoDeliveryError):
        parse_delivery(payload, "1234567")


@pytest.mark.parametrize("payload", [None, [], "html", 42])
def test_non_object_response(payload):
    with pytest.raises(VolvoDeliveryError):
        parse_delivery(payload, "1234567")


def session_with_response(status, payload):
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=deepcopy(payload))
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    session = MagicMock()
    session.get.return_value = request
    return session, response


async def test_client_success(payload):
    session, _ = session_with_response(200, payload)
    data = await VolvoDeliveryClient(
        session, "1234567", "example-token"
    ).async_get_delivery()
    assert data.status == "Order placed"
    session.get.assert_called_once_with(
        "https://order-delivery-backend.vcscloud.se/markets/se/orders/1234567",
        headers={"Authorization": "Bearer example-token", "Accept": "application/json"},
        allow_redirects=False,
    )


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, VolvoDeliveryAuthError),
        (403, VolvoDeliveryAuthError),
        (404, VolvoDeliveryOrderNotFound),
        (429, VolvoDeliveryError),
        (500, VolvoDeliveryError),
        (302, VolvoDeliveryError),
    ],
)
async def test_http_errors(status, error, payload):
    session, response = session_with_response(status, payload)
    with pytest.raises(error) as raised:
        await VolvoDeliveryClient(
            session, "1234567", "example-token"
        ).async_get_delivery()
    assert "example-token" not in str(raised.value)
    assert "1234567" not in str(raised.value)
    response.json.assert_not_called()


@pytest.mark.parametrize("error", [ClientConnectionError(), TimeoutError()])
async def test_transport_errors(error):
    session = MagicMock()
    session.get.side_effect = error
    with pytest.raises(VolvoDeliveryError):
        await VolvoDeliveryClient(
            session, "1234567", "example-token"
        ).async_get_delivery()


async def test_non_json_error(payload):
    session, response = session_with_response(200, payload)
    response.json.side_effect = ValueError("Invalid JSON")
    with pytest.raises(VolvoDeliveryError):
        await VolvoDeliveryClient(
            session, "1234567", "example-token"
        ).async_get_delivery()
