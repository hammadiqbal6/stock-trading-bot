"""US equity market hours and holiday awareness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from trading_bot.utils.logging import get_logger

logger = get_logger(__name__)
ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class SessionInfo:
    is_open: bool
    is_trading_day: bool
    now_et: datetime
    next_open: datetime | None
    next_close: datetime | None
    guidance: str


class MarketCalendar:
    """NYSE calendar wrapper with graceful fallback if calendars unavailable."""

    def __init__(self, calendar_name: str = "XNYS") -> None:
        self.calendar_name = calendar_name
        self._cal: Any | None = None
        try:
            import exchange_calendars as xcals

            self._cal = xcals.get_calendar(calendar_name)
        except Exception as exc:
            logger.warning(
                "exchange_calendars_unavailable",
                error=str(exc),
                guidance="Falling back to weekday 09:30–16:00 ET heuristic (holidays ignored).",
            )

    def now_et(self) -> datetime:
        return datetime.now(ET)

    def session_info(self, when: datetime | None = None) -> SessionInfo:
        now = when.astimezone(ET) if when else self.now_et()
        if self._cal is not None:
            try:
                is_trading_day = bool(self._cal.is_session(now.date()))
                is_open = bool(self._cal.is_open_on_minute(now))
                next_open = self._cal.next_open(now)
                next_close = self._cal.next_close(now)
                # exchange_calendars returns tz-aware timestamps
                no = next_open.to_pydatetime() if hasattr(next_open, "to_pydatetime") else next_open
                nc = (
                    next_close.to_pydatetime()
                    if hasattr(next_close, "to_pydatetime")
                    else next_close
                )
                if is_open:
                    guidance = f"Market open. Regular close around {nc.astimezone(ET):%H:%M %Z}."
                elif is_trading_day:
                    guidance = (
                        f"Trading day but outside regular hours. Next open/close: "
                        f"{no.astimezone(ET):%Y-%m-%d %H:%M %Z} / {nc.astimezone(ET):%H:%M %Z}."
                    )
                else:
                    guidance = (
                        f"Market holiday or weekend. Next regular open: "
                        f"{no.astimezone(ET):%Y-%m-%d %H:%M %Z}."
                    )
                return SessionInfo(
                    is_open=is_open,
                    is_trading_day=is_trading_day,
                    now_et=now,
                    next_open=no,
                    next_close=nc,
                    guidance=guidance,
                )
            except Exception as exc:
                logger.warning("calendar_query_failed", error=str(exc))

        return self._fallback(now)

    def is_open(self, when: datetime | None = None) -> bool:
        return self.session_info(when).is_open

    def is_trading_day(self, d: date | None = None) -> bool:
        d = d or self.now_et().date()
        if self._cal is not None:
            try:
                return bool(self._cal.is_session(d))
            except Exception:
                pass
        return d.weekday() < 5

    def _fallback(self, now: datetime) -> SessionInfo:
        weekday = now.weekday() < 5
        open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
        is_open = weekday and open_t <= now <= close_t
        if is_open:
            guidance = "Market likely open (fallback calendar; holidays not detected)."
            next_open, next_close = open_t, close_t
        elif weekday and now < open_t:
            guidance = "Before open (fallback calendar)."
            next_open, next_close = open_t, close_t
        else:
            # next weekday 09:30
            days = 1
            candidate = now
            while True:
                from datetime import timedelta

                candidate = (now + timedelta(days=days)).replace(
                    hour=9, minute=30, second=0, microsecond=0
                )
                if candidate.weekday() < 5:
                    break
                days += 1
            next_open = candidate
            next_close = candidate.replace(hour=16, minute=0)
            guidance = (
                f"Market closed (fallback). Approx next open {next_open:%Y-%m-%d %H:%M %Z}. "
                "Install/fix exchange-calendars for holiday accuracy."
            )
        return SessionInfo(
            is_open=is_open,
            is_trading_day=weekday,
            now_et=now,
            next_open=next_open,
            next_close=next_close,
            guidance=guidance,
        )
