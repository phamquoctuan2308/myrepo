"""Time-warp clock for the FlowCrew hero flow.

Every agent reads time from here, so the 14:05 → 14:30 scenario in the charter
replays identically on any afternoon and "quá tải trong 25 phút" is measured in
simulated minutes rather than whenever the demo happens to run.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

# Fixed offset on purpose: Windows Python ships no IANA database, and Vietnam
# has not observed daylight saving since 1975.
VN_TZ = timezone(timedelta(hours=7), "ICT")

PARK_DATE = datetime(2026, 9, 16, tzinfo=VN_TZ).date()
DEFAULT_START = datetime(2026, 9, 16, 14, 0, tzinfo=VN_TZ)


class SimClock:
    def __init__(self, start: datetime = DEFAULT_START) -> None:
        if start.tzinfo is None:
            raise ValueError("Mốc bắt đầu mô phỏng phải có múi giờ")
        self._now = start

    @property
    def now(self) -> datetime:
        return self._now

    def advance(self, minutes: float) -> datetime:
        if minutes < 0:
            raise ValueError("Thời gian mô phỏng không chạy ngược")
        self._now += timedelta(minutes=minutes)
        return self._now

    def jump_to(self, clock_time: time) -> datetime:
        """Move forward to a wall-clock time on the simulated park day."""

        target = datetime.combine(self._now.date(), clock_time, tzinfo=VN_TZ)
        if target < self._now:
            raise ValueError(f"{clock_time} đã trôi qua trong ngày mô phỏng")
        self._now = target
        return self._now


def at(hour: int, minute: int = 0) -> datetime:
    """A moment on the simulated park day; the seed data is written in these."""

    return datetime(PARK_DATE.year, PARK_DATE.month, PARK_DATE.day, hour, minute, tzinfo=VN_TZ)


def minutes_between(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 60, 1)


def hhmm(moment: datetime) -> str:
    return moment.astimezone(VN_TZ).strftime("%H:%M")
