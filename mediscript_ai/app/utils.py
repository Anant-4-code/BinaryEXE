"""Utility functions for display."""

# People-friendly display for medical frequency abbreviations
FREQUENCY_DISPLAY = {
    "od": "Once daily",
    "bd": "Twice daily",
    "bid": "Twice daily",
    "tds": "Three times daily",
    "tid": "Three times daily",
    "qid": "Four times daily",
    "q4h": "Every 4 hours",
    "q6h": "Every 6 hours",
    "hs": "At bedtime",
    "prn": "As needed",
    "sos": "If necessary",
}


def format_frequency(freq) -> str:
    """Convert medical frequency abbreviations to people-friendly text."""
    if freq is None or (isinstance(freq, str) and not freq.strip()):
        return "—"
    key = str(freq).lower().strip()
    return FREQUENCY_DISPLAY.get(key, str(freq).strip())
