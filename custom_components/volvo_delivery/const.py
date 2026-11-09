"""Constants for Volvo delivery tracking."""

from datetime import timedelta

DOMAIN = "volvo_delivery"
CONF_AUTHORIZATION = "authorization"
CONF_ORDER_NUMBER = "order_number"
DELIVERY_URL = "https://www.volvocars.com/se/delivery-information/"
API_URL = "https://order-delivery-backend.vcscloud.se/markets/se/orders"
UPDATE_INTERVAL = timedelta(days=1)
CARD_URL = "/volvo_delivery/volvo-delivery-card.js?v=0.3.0"
