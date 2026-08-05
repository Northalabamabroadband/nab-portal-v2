import pytest

from app.modules.platform.router import admin_capabilities
from app.modules.tauc.client import (
    is_tauc_rate_limited,
    should_retry_tauc_request,
    tauc_request_delay,
)


def test_tauc_requests_are_spaced_beyond_one_second() -> None:
    assert tauc_request_delay(10.0, 10.20, 1.05) == pytest.approx(0.85)
    assert tauc_request_delay(10.0, 11.20, 1.05) == 0.0


def test_tauc_provider_rate_limit_is_detected() -> None:
    payload = {
        "errorCode": -70307,
        "msg": "The visit count of this api has reached the rate limit",
    }
    assert is_tauc_rate_limited(200, payload) is True
    assert is_tauc_rate_limited(429, {}) is True


def test_only_first_rate_limited_get_is_retried() -> None:
    payload = {"errorCode": "-70307"}
    assert should_retry_tauc_request("GET", 200, payload, 0) is True
    assert should_retry_tauc_request("GET", 200, payload, 1) is False
    assert should_retry_tauc_request("POST", 200, payload, 0) is False


def test_tauc_throttle_is_reported() -> None:
    capabilities = admin_capabilities({})
    assert capabilities["features"]["tauc_request_throttle"] == (
        "one-per-second-with-safe-get-retry"
    )
