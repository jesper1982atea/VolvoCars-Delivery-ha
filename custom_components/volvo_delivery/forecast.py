"""Turn a Volvo delivery week into an explicitly estimated ISO week interval."""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .api import DeliveryData


@dataclass(frozen=True)
class DeliveryForecast:
    """Calendar boundaries, never an exact delivery promise."""

    start: date
    end: date
    week: int
    year: int
    year_source: str


def delivery_forecast(data: DeliveryData, reference: date) -> DeliveryForecast | None:
    """Infer a year only when Volvo's weeks-remaining text supports it."""
    text = data.delivery_estimate or ""
    matches = list(re.finditer(r"\b(?:v\.?|vecka)\s*(\d{1,2})\b", text, re.I))
    if len(matches) != 1:
        return None
    match = matches[0]
    if re.match(r"\s*(?:[-–/]|till|och|eller)\s*\d", text[match.end() :], re.I):
        return None
    week = int(match[1])
    years = re.findall(r"\b(20\d{2})\b", text)
    if len(years) > 1:
        return None
    if years:
        year = int(years[0])
        try:
            start = date.fromisocalendar(year, week, 1)
        except ValueError:
            return None
        source = "volvo"
    else:
        remaining = re.search(
            r"\b(\d{1,3})\s+veck(?:a|or)\s+kvar\b",
            data.delivery_estimate_title or "",
            re.I,
        )
        if remaining is None or int(remaining[1]) > 104:
            return None
        target = reference + timedelta(weeks=int(remaining[1]))
        candidates = []
        for year in range(reference.year - 1, reference.year + 4):
            try:
                candidates.append(date.fromisocalendar(year, week, 1))
            except ValueError:
                continue
        if not candidates:
            return None
        start = min(candidates, key=lambda day: abs((day - target).days))
        if abs((start - target).days) > 21:
            return None
        year = start.isocalendar().year
        source = "inferred"
    return DeliveryForecast(
        start=start,
        end=start + timedelta(days=6),
        week=week,
        year=year,
        year_source=source,
    )
