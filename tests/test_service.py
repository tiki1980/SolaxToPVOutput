import logging

import requests

from solaxtopvoutput.config import (
    AppConfig,
    Config,
    PVOutputConfig,
    SolaxCloudConfig,
)
from solaxtopvoutput.service import (
    UploadResult,
    build_pvoutput_payload,
    calculate_sleep_seconds,
    get_real_time_solax_data,
    run_forever,
    upload_to_pvoutput,
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


def test_run_forever_uses_backoff_after_repeated_failures(
    monkeypatch,
) -> None:
    config = Config(
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
        config_path="dummy.yml",
    )
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
