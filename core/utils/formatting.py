from __future__ import annotations

from core.utils.jalali import PERSIAN_DIGITS_TRANS


def format_money(value) -> str:
    """Format integer money with Persian digits and Persian thousands separator."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""

    return f"{number:,}".replace(",", "،").translate(PERSIAN_DIGITS_TRANS)

