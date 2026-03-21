import logging

import requests

from solaxtopvoutput.config import (
    PVOutputConfig,
    SolaxCloudConfig,
)
from solaxtopvoutput.service import (
    build_pvoutput_payload,
    get_real_time_solax_data,
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
