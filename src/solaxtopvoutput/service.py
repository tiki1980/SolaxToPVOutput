"""Core SolaxCloud and PVOutput service logic."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from .config import Config, PVOutputConfig, SolaxCloudConfig
from .sun_window import seconds_until_window_opens, should_poll_now

SOLAX_DUMMY_RESPONSE: dict[str, Any] = {
    "success": False,
    "exception": "Query failure!",
    "result": {
        "inverterSN": "",
        "sn": "",
        "acpower": 0,
        "yieldtoday": 0,
        "yieldtotal": 0,
        "feedinpower": 0,
        "feedinenergy": 0,
        "consumeenergy": 0,
        "feedinpowerM2": 0,
        "soc": 0,
        "peps1": 0,
        "peps2": 0,
        "peps3": 0,
        "inverterType": "4",
        "inverterStatus": "0",
        "uploadTime": "1970-01-01 00:00:00",
        "batPower": 0,
        "powerdc1": 0,
        "powerdc2": 0,
        "powerdc3": 0,
        "powerdc4": 0,
        "batStatus": 0,
    },
    "code": 0,
}

MAX_BACKOFF_MULTIPLIER = 5


@dataclass(frozen=True)
class UploadResult:
    """PVOutput upload result."""

    ok: bool
    status_code: int | None
    text: str


def get_real_time_solax_data(
    solax_config: SolaxCloudConfig,
    session: requests.Session,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Call the SolaxCloud realtime API."""

    api_url = (
        f"{solax_config.api_url.rstrip('/')}"
        "/api/v2/dataAccess/realtimeInfo/get"
    )
    headers = {
        "tokenId": solax_config.token_id,
        "Content-Type": "application/json",
    }
    payload = {"wifiSn": solax_config.registration_nr}

    logger.debug("Solax API url: %s", api_url)
    try:
        response = session.post(
            api_url, headers=headers, json=payload, timeout=10
        )
        response.raise_for_status()
        logger.debug("Solax response status code: %s", response.status_code)
        logger.info("Solax response body: %s", response.text)
        return response.json()
    except requests.exceptions.RequestException:
        logger.exception("Solax request failed")
        return SOLAX_DUMMY_RESPONSE.copy()


def build_pvoutput_payload(solax_data: dict[str, Any]) -> dict[str, str]:
    """Convert a successful Solax response into a PVOutput payload."""

    result = solax_data.get("result")
    if not isinstance(result, dict):
        raise ValueError("Solax response did not contain a result object")

    upload_time = str(result.get("uploadTime", "")).strip()
    try:
        upload_dt = datetime.strptime(upload_time, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"Invalid uploadTime value: {upload_time!r}") from exc

    gen_tot_wh = _kwh_to_wh(result.get("yieldtotal"))
    gen_pwr = _to_int(result.get("acpower"))
    consume_energy = result.get("consumeenergy")
    feedin_power = result.get("feedinpower")

    cons_tot_wh = 0
    if consume_energy is not None:
        cons_tot_wh = _kwh_to_wh(consume_energy)

    con_pwr = 0
    if feedin_power is not None:
        con_pwr = max(gen_pwr - _to_int(feedin_power), 0)

    return {
        "d": upload_dt.strftime("%Y%m%d"),
        "t": upload_dt.strftime("%H:%M"),
        "v1": str(gen_tot_wh),
        "v2": str(gen_pwr),
        "v3": str(cons_tot_wh),
        "v4": str(con_pwr),
        "c1": "1",
    }


def upload_to_pvoutput(
    pvoutput_config: PVOutputConfig,
    pvoutput_data: dict[str, str],
    session: requests.Session,
    logger: logging.Logger,
) -> UploadResult:
    """Upload a status payload to PVOutput."""

    api_url = "https://pvoutput.org/service/r2/addstatus.jsp"
    headers = {
        "X-Pvoutput-SystemId": str(pvoutput_config.system_id),
        "X-Pvoutput-Apikey": pvoutput_config.api_key,
    }

    logger.debug("PVOutput API url: %s", api_url)
    logger.info("PVOutput payload: %s", pvoutput_data)
    try:
        response = session.post(
            api_url, headers=headers, data=pvoutput_data, timeout=10
        )
        response.raise_for_status()
        logger.info("PVOutput status code: %s", response.status_code)
        logger.debug("PVOutput response: %s", response.text)
        return UploadResult(
            ok=True, status_code=response.status_code, text=response.text
        )
    except requests.exceptions.RequestException as exc:
        status_code = None
        body = str(exc)
        if exc.response is not None:
            status_code = exc.response.status_code
            body = exc.response.text
        logger.exception("PVOutput upload failed")
        return UploadResult(ok=False, status_code=status_code, text=body)


def poll_once(
    config: Config,
    session: requests.Session,
    logger: logging.Logger,
) -> UploadResult | None:
    """Fetch Solax data and upload it to PVOutput when possible."""

    solax_data = get_real_time_solax_data(config.solax_cloud, session, logger)
    if not solax_data.get("success"):
        logger.error("SolaxCloud returned failure payload")
        logger.error("%s", solax_data)
        return None

    pvoutput_payload = build_pvoutput_payload(solax_data)
    return upload_to_pvoutput(
        config.pvoutput, pvoutput_payload, session, logger
    )


def calculate_sleep_seconds(
    base_interval: int,
    consecutive_failures: int,
) -> int:
    """Calculate the next polling delay with capped backoff."""

    if consecutive_failures <= 0:
        return base_interval

    multiplier = min(2 ** (consecutive_failures - 1), MAX_BACKOFF_MULTIPLIER)
    return base_interval * multiplier


def run_forever(
    config: Config,
    logger: logging.Logger,
    session: requests.Session | None = None,
    sleep_fn=time.sleep,
) -> int:
    """Run the poll-upload loop until interrupted."""

    active_session = session or requests.Session()
    consecutive_failures = 0
    logger.info("Started SolaxToPVOutput")
    try:
        while True:
            if not should_poll_now(config, logger):
                sleep_seconds = seconds_until_window_opens(config)
                logger.debug(
                    "Outside configured sun window, sleeping for %s seconds",
                    sleep_seconds,
                )
                sleep_fn(sleep_seconds)
                continue

            try:
                result = poll_once(config, active_session, logger)
                if result is None or not result.ok:
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
            except ValueError:
                consecutive_failures += 1
                logger.exception(
                    "Invalid data received while processing a polling cycle"
                )

            sleep_seconds = calculate_sleep_seconds(
                config.app.poll_interval_seconds,
                consecutive_failures,
            )
            logger.debug("Sleeping for %s seconds", sleep_seconds)
            sleep_fn(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping SolaxToPVOutput")
        return 0
    finally:
        if session is None:
            active_session.close()


def _kwh_to_wh(value: Any) -> int:
    return int(round(float(value) * 1000))


def _to_int(value: Any) -> int:
    return int(round(float(value)))
