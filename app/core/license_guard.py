from __future__ import annotations

from datetime import date, datetime, timedelta


class LicenseExpiredError(RuntimeError):
    """Raised when prototype usage period is over."""


def enforce_runtime_window(start_date_iso: str, valid_days: int = 90) -> None:
    start = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
    expiry = start + timedelta(days=valid_days)
    today = date.today()
    if today > expiry:
        raise LicenseExpiredError(
            f"Срок действия прототипа истёк: {expiry.isoformat()}"
        )
