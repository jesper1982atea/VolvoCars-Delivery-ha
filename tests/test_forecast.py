"""Verify ISO weeks, year inference and ambiguity without invented dates."""

from dataclasses import replace
from datetime import date

import pytest

from custom_components.volvo_delivery.api import parse_delivery
from custom_components.volvo_delivery.forecast import delivery_forecast


def forecast(payload, text, title, reference=date(2026, 11, 9)):
    data = replace(
        parse_delivery(payload, "1234567"),
        delivery_estimate=text,
        delivery_estimate_title=title,
    )
    return delivery_forecast(data, reference)


def test_swedish_week_and_remaining_cross_year(payload):
    result = forecast(
        payload, "Leverans beräknad till v. 5", "12 veckor kvar till beräknad leverans"
    )
    assert result.start == date(2027, 2, 1)
    assert result.end == date(2027, 2, 7)
    assert result.year == 2027
    assert result.week == 5
    assert result.year_source == "inferred"
    assert (result.start - date(2026, 11, 9)).days == 84


@pytest.mark.parametrize("text", ["Leverans v. 5 2027", "Leverans vecka 5, 2027"])
def test_explicit_year_needs_no_countdown(payload, text):
    result = forecast(payload, text, None)
    assert result.start == date(2027, 2, 1)
    assert result.year_source == "volvo"


def test_iso_week_crosses_calendar_year(payload):
    result = forecast(payload, "Leverans v. 1 2026", None)
    assert result.start == date(2025, 12, 29)
    assert result.end == date(2026, 1, 4)
    assert result.year == 2026


@pytest.mark.parametrize(
    ("text", "title"),
    [
        (None, None),
        ("Kontakta din säljare", "12 veckor kvar"),
        ("Leverans v. 5", None),
        ("Leverans v. 5", "Okänt antal veckor"),
        ("Leverans v. 5", "105 veckor kvar"),
        ("Leverans v. 5", "1 vecka kvar"),
        ("Leverans v. 0 2027", None),
        ("Leverans v. 54 2027", None),
        ("Leverans v. 53 2027", None),
        ("Leverans v. 5-6 2027", None),
        ("Leverans v. 5–6 2027", None),
        ("Leverans v. 5/6 2027", None),
        ("Leverans v. 5 till 6 2027", None),
        ("Leverans v. 5 eller v. 6", "12 veckor kvar"),
        ("Leverans v. 5 2027 eller 2028", None),
    ],
)
def test_unknown_or_conflicting_input_has_no_forecast(payload, text, title):
    assert forecast(payload, text, title) is None


def test_valid_week_53(payload):
    result = forecast(payload, "Leverans v. 53 2026", None)
    assert result.start == date(2026, 12, 28)
    assert result.end == date(2027, 1, 3)


def test_zero_weeks_current_week(payload):
    result = forecast(
        payload, "Leverans v. 46", "0 veckor kvar", reference=date(2026, 11, 11)
    )
    assert result.start == date(2026, 11, 9)
