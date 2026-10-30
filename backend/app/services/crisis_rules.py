"""Deterministic crisis recognition rules that run before any AI call."""
import re

from app.validators.schemas import CrisisIntent


def parse_known_crisis(description: str, event_date: str | None) -> CrisisIntent | None:
    """Recognize supported changes with deterministic rules before any AI call."""
    text = description.casefold()
    if "cater" in text and re.search(r"\b(cancel(?:ed|led)?|withdrawn|dropped)\b", text):
        return CrisisIntent(kind="caterer_cancelled")
    if re.search(r"\b(rain|raining|weather|storm|outdoor)\b", text):
        return CrisisIntent(kind="weather_risk")

    if re.search(r"\b(guest|guests|attendee|attendees|headcount|people)\b", text):
        range_match = re.search(r"\bfrom\s+(\d+)\s+to\s+(\d+)\b", text)
        target_match = re.search(r"\bto\s+(\d+)\b", text)
        if range_match or target_match:
            target_count = int(range_match.group(2) if range_match else target_match.group(1))
            return CrisisIntent(kind="guest_count_change", new_guest_count=target_count)

    if event_date and re.search(r"\b(move|moved|advance|advanced|earlier|up)\b", text):
        match = re.search(r"\b(\d{1,3})\s*(day|days|week|weeks|month|months)\b", text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            days = amount * (30 if unit.startswith("month") else 7 if unit.startswith("week") else 1)
            if 1 <= days <= 365:
                return CrisisIntent(kind="date_advanced", days_advanced=days)
    return None
