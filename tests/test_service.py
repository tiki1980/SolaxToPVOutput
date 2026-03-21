import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from solaxtopvoutput.config import (
    AppConfig,
    Config,
    PVOutputConfig,
    SolaxCloudConfig,
    SunWindowConfig,
)
from solaxtopvoutput.service import (
    UploadResult,
    build_pvoutput_payload,
    calculate_sleep_seconds,
    get_real_time_solax_data,
    run_forever,
    upload_to_pvoutput,
)
from solaxtopvoutput.sun_window import (
    seconds_until_window_opens,
    should_poll_now,
)


class DummyResponse:
    def __init__(
        self,
        status_code=200,
        text="OK",
        json_payload=None,
    ):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._json_payload


class DummySession:
    def __init__(
        self,
        get_response=None,
        post_response=None,
        get_exception=None,
        post_exception=None,
    ):
        self.get_response = get_response
        self.post_response = post_response
        self.get_exception = get_exception
        self.post_exception = post_exception

    def get(self, *args, **kwargs):
        if self.get_exception is not None:
            raise self.get_exception
        return self.get_response

    def post(self, *args, **kwargs):
        if self.post_exception is not None:
            raise self.post_exception
        return self.post_response


class SequencePoller:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def __call__(self, config, session, logger):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def build_config(*, sun_window: SunWindowConfig | None = None) -> Config:
    return Config(
        app=AppConfig(
            log_level="INFO",
            poll_interval_seconds=60,
            log_file="test.log",
        ),
        solax_cloud=SolaxCloudConfig(
            api_url="https://global.solaxcloud.com",
            token_id="token",
            registration_nr="wifi",
        ),
        pvoutput=PVOutputConfig(system_id=123, api_key="key"),
        sun_window=sun_window or SunWindowConfig(),
        config_path="dummy.yml",
    )


def test_build_pvoutput_payload_maps_fields() -> None:
    payload = build_pvoutput_payload(
        {
            "success": True,
            "result": {
                "yieldtotal": 12.3,
                "acpower": 2670,
                "consumeenergy": 22.2,
                "feedinpower": 2527,
                "uploadTime": "2025-05-05 19:50:00",
            },
        }
    )

    assert payload == {
        "d": "20250505",
        "t": "19:50",
        "v1": "12300",
        "v2": "2670",
        "v3": "22200",
        "v4": "143",
        "c1": "1",
    }


def test_calculate_sleep_seconds_caps_backoff() -> None:
    assert calculate_sleep_seconds(60, 0) == 60
    assert calculate_sleep_seconds(60, 1) == 60
    assert calculate_sleep_seconds(60, 2) == 120
    assert calculate_sleep_seconds(60, 4) == 300
    assert calculate_sleep_seconds(60, 8) == 300


def test_get_real_time_solax_data_returns_dummy_response_on_failure() -> None:
    session = DummySession(post_exception=requests.RequestException("boom"))
    logger = logging.getLogger("test")

    result = get_real_time_solax_data(
        SolaxCloudConfig(
            api_url="https://global.solaxcloud.com",
            token_id="token",
            registration_nr="wifi",
        ),
        session,
        logger,
    )

    assert result["success"] is False


def test_upload_to_pvoutput_returns_failure_without_unbound_error() -> None:
    session = DummySession(post_exception=requests.RequestException("boom"))
    logger = logging.getLogger("test")

    result = upload_to_pvoutput(
        PVOutputConfig(system_id=123, api_key="key"),
        {"d": "20250505"},
        session,
        logger,
    )

    assert result.ok is False
    assert result.status_code is None
    assert "boom" in result.text


def test_should_poll_now_obeys_window(monkeypatch) -> None:
    config = build_config(
        sun_window=SunWindowConfig(
            enabled=True,
            latitude=52.1326,
            longitude=5.2913,
            timezone="Europe/Amsterdam",
            start_event="dawn",
            end_event="sunset",
        )
    )
    logger = logging.getLogger("test")
    timezone = ZoneInfo("Europe/Amsterdam")

    monkeypatch.setattr(
        "solaxtopvoutput.sun_window._sun_window_for_date",
        lambda config, _: {
            "dawn": datetime(2026, 3, 21, 6, 0, tzinfo=timezone),
            "sunrise": datetime(2026, 3, 21, 6, 30, tzinfo=timezone),
            "sunset": datetime(2026, 3, 21, 18, 30, tzinfo=timezone),
            "dusk": datetime(2026, 3, 21, 19, 0, tzinfo=timezone),
        },
    )

    assert should_poll_now(
        config,
        logger,
        now=datetime(2026, 3, 21, 12, 0, tzinfo=timezone),
    )
    assert not should_poll_now(
        config,
        logger,
        now=datetime(2026, 3, 21, 5, 0, tzinfo=timezone),
    )


def test_seconds_until_window_opens_returns_next_start(monkeypatch) -> None:
    config = build_config(
        sun_window=SunWindowConfig(
            enabled=True,
            latitude=52.1326,
            longitude=5.2913,
            timezone="Europe/Amsterdam",
            start_event="sunrise",
            end_event="sunset",
        )
    )
    timezone = ZoneInfo("Europe/Amsterdam")

    monkeypatch.setattr(
        "solaxtopvoutput.sun_window._sun_window_for_date",
        lambda config, target_date: {
            "dawn": datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                6,
                0,
                tzinfo=timezone,
            ),
            "sunrise": datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                6,
                30,
                tzinfo=timezone,
            ),
            "sunset": datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                18,
                30,
                tzinfo=timezone,
            ),
            "dusk": datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                19,
                0,
                tzinfo=timezone,
            ),
        },
    )

    seconds = seconds_until_window_opens(
        config,
        now=datetime(2026, 3, 21, 5, 30, tzinfo=timezone),
    )

    assert seconds == 3600


def test_run_forever_uses_backoff_after_repeated_failures(monkeypatch) -> None:
    config = build_config()
    logger = logging.getLogger("test")
    sleeps = []
    poller = SequencePoller(
        [
            None,
            UploadResult(False, 500, "fail"),
            ValueError("bad payload"),
            KeyboardInterrupt(),
        ]
    )

    monkeypatch.setattr("solaxtopvoutput.service.poll_once", poller)

    exit_code = run_forever(
        config,
        logger,
        session=DummySession(),
        sleep_fn=sleeps.append,
    )

    assert exit_code == 0
    assert sleeps == [60, 120, 240]


def test_run_forever_skips_polling_outside_sun_window(monkeypatch) -> None:
    config = build_config(
        sun_window=SunWindowConfig(
            enabled=True,
            latitude=52.1326,
            longitude=5.2913,
            timezone="Europe/Amsterdam",
            start_event="sunrise",
            end_event="sunset",
        )
    )
    logger = logging.getLogger("test")
    sleeps = []

    monkeypatch.setattr(
        "solaxtopvoutput.service.should_poll_now",
        lambda config, logger: False,
    )
    monkeypatch.setattr(
        "solaxtopvoutput.service.seconds_until_window_opens",
        lambda config: 1800,
    )
    monkeypatch.setattr(
        "solaxtopvoutput.service.poll_once",
        lambda config, session, logger: UploadResult(True, 200, "OK"),
    )

    def fake_sleep(seconds):
        sleeps.append(seconds)
        raise KeyboardInterrupt

    exit_code = run_forever(
        config,
        logger,
        session=DummySession(),
        sleep_fn=fake_sleep,
    )

    assert exit_code == 0
    assert sleeps == [1800]
