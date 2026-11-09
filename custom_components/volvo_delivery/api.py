"""Client for the backend used by Volvo's Swedish delivery page."""

import asyncio
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ContentTypeError

from .const import API_URL


class VolvoDeliveryError(Exception):
    """The delivery service could not be reached or understood."""


class VolvoDeliveryAuthError(VolvoDeliveryError):
    """The authorization value is no longer accepted."""


class VolvoDeliveryOrderNotFound(VolvoDeliveryError):
    """The order is not available in the delivery service."""


def valid_order_number(value: str) -> bool:
    """Accept the seven or eight ASCII digits supported by Volvo's form."""
    return re.fullmatch(r"[0-9]{7,8}", value) is not None


def normalize_authorization(value: str) -> str:
    """Accept either the complete Bearer header or just its token."""
    if "\r" in value or "\n" in value:
        raise ValueError("Invalid authorization value")
    value = value.strip()
    if not value or value.lower() == "bearer":
        raise ValueError("Invalid authorization value")
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if not value or any(char.isspace() for char in value):
        raise ValueError("Invalid authorization value")
    return f"Bearer {value}"


@dataclass(frozen=True)
class DeliveryData:
    """Only delivery fields; never retain sales contact details."""

    status: str
    delivery_estimate: str | None
    delivery_estimate_title: str | None
    order_changes: str | None
    order_changes_description: str | None
    model: str | None
    specification: str | None
    image_url: str | None = None
    image_alt: str | None = None
    rear_image_url: str | None = None
    interior_image_url: str | None = None
    model_url: str | None = None
    manual_url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-compatible data for persistent change detection."""
        return asdict(self)


def volvo_url(value: str | None, *, image: bool = False) -> str | None:
    """Only expose HTTPS assets and pages on the hosts used by Volvo."""
    if not value:
        return None
    hosts = (
        {"wizz.volvocars.com", "www.volvocars.com", "dam.fbinhouse.se"}
        if image
        else {"www.volvocars.com"}
    )
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "https"
            and url.hostname in hosts
            and url.username is None
            and url.password is None
            and url.port in (None, 443)
        )
    except ValueError:
        valid = False
    if not valid:
        raise VolvoDeliveryError("Unexpected Volvo image or page URL")
    return value


def parse_delivery(payload: Any, order_number: str) -> DeliveryData:
    """Parse the response fields used by the delivery page."""
    if not isinstance(payload, dict):
        raise VolvoDeliveryError("Unexpected delivery response")
    returned_order = payload.get("orderNumber")
    if isinstance(returned_order, bool) or not (
        returned_order == order_number
        or (isinstance(returned_order, int) and returned_order == int(order_number))
    ):
        raise VolvoDeliveryError("Delivery response does not match the order")

    def text(section: str, key: str) -> str | None:
        value = payload.get(section)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise VolvoDeliveryError("Unexpected delivery field")
        result = value.get(key)
        if result is None:
            return None
        if not isinstance(result, str):
            raise VolvoDeliveryError("Unexpected delivery text")
        return result.strip() or None

    status = text("status", "copy")
    if status is None:
        raise VolvoDeliveryError("Delivery response is missing its status")
    return DeliveryData(
        status=status,
        delivery_estimate=text("deliveryDateEstimate", "copy"),
        delivery_estimate_title=text("deliveryDateEstimate", "title"),
        order_changes=text("changeOrder", "title"),
        order_changes_description=text("changeOrder", "copy"),
        model=text("car", "modelDescription"),
        specification=text("car", "carSpecificationString"),
        image_url=volvo_url(text("car", "infoImg"), image=True),
        image_alt=text("car", "altText"),
        rear_image_url=volvo_url(text("car", "getToKnowImg"), image=True),
        interior_image_url=volvo_url(text("car", "manualImg"), image=True),
        model_url=volvo_url(text("car", "infoHref")),
        manual_url=volvo_url(text("car", "manualHref")),
    )


class VolvoDeliveryClient:
    """Fetch one order without scraping the HTML page."""

    def __init__(
        self, session: ClientSession, order_number: str, authorization: str
    ) -> None:
        if not valid_order_number(order_number):
            raise ValueError("Invalid order number")
        self._session = session
        self._order_number = order_number
        self._authorization = normalize_authorization(authorization)

    async def async_get_delivery(self) -> DeliveryData:
        """Fetch current data; do not include credentials in errors."""
        try:
            async with asyncio.timeout(30):
                async with self._session.get(
                    f"{API_URL}/{self._order_number}",
                    headers={
                        "Authorization": self._authorization,
                        "Accept": "application/json",
                    },
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        raise VolvoDeliveryAuthError("Authorization rejected")
                    if response.status == 404:
                        raise VolvoDeliveryOrderNotFound("Order not found")
                    if response.status != 200:
                        raise VolvoDeliveryError(
                            f"Delivery service returned HTTP {response.status}"
                        )
                    payload = await response.json()
        except (ClientError, TimeoutError, ContentTypeError, ValueError) as err:
            raise VolvoDeliveryError(
                "Unable to read delivery service response"
            ) from err
        return parse_delivery(payload, self._order_number)
