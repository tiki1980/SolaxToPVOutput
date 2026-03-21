"""Sun-window calculations for poll scheduling."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astral import Depression
from astral.sun import Observer, sun

from .config import Config


def should_poll_now(
    config: Config,
    logger: logging.Logger,
    now: datetime | None = None,
) -> bool:
    """Return whether current time falls inside the configured sun window."""

    if not config.sun_window.enabled:
        return True

    current_time = _localized_now(config, now)
    window = _sun_window_for_date(config, current_time.date())
    start_time = window[config.sun_window.start_event]
    end_time = window[config.sun_window.end_event]
    in_window = start_time <= current_time <= end_time
    logger.debug(
        "Sun window check at %s returned %s",
        current_time.isoformat(),
        in_window,
    )
    return in_window


def seconds_until_window_opens(
    config: Config,
    now: datetime | None = None,
) -> int:
    """Return seconds until the next configured sun-window start."""

    if not config.sun_window.enabled:
        return config.app.poll_interval_seconds

    current_time = _localized_now(config, now)
    current_window = _sun_window_for_date(config, current_time.date())
    start_time = current_window[config.sun_window.start_event]

    if current_time < start_time:
        return _seconds_between(current_time, start_time)

    next_day = current_time.date() + timedelta(days=1)
    next_window = _sun_window_for_date(config, next_day)
    next_start = next_window[config.sun_window.start_event]
    return _seconds_between(current_time, next_start)


def _localized_now(config: Config, now: datetime | None) -> datetime:
    timezone = ZoneInfo(config.sun_window.timezone)
    if now is None:
        return datetime.now(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone)
    return now.astimezone(timezone)


def _sun_window_for_date(config: Config, target_date) -> dict[str, datetime]:
    observer = Observer(
        latitude=config.sun_window.latitude,
        longitude=config.sun_window.longitude,
    )
    timezone = ZoneInfo(config.sun_window.timezone)
    return sun(
        observer,
        date=target_date,
        tzinfo=timezone,
        dawn_dusk_depression=Depression.CIVIL,
    )


def _seconds_between(start: datetime, end: datetime) -> int:
    return max(int((end - start).total_seconds()), 0)
