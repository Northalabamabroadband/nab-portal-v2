from app.modules.tauc.client import tauc_error_message


def test_tauc_404_identifies_endpoint_configuration() -> None:
    message = tauc_error_message(
        404,
        "get",
        "https://use1-tauc-openapi.tplinkcloud.com",
        "/v1/openapi/device-information/device-id",
        {},
        "Not Found",
    )
    assert "TAUC endpoint not found" in message
    assert "GET https://use1-tauc-openapi.tplinkcloud.com" in message
    assert "TAUC_BASE_URL" in message
    assert "lookup path" in message


def test_non_404_tauc_errors_keep_provider_code_and_message() -> None:
    message = tauc_error_message(
        401,
        "get",
        "https://use1-tauc-openapi.tplinkcloud.com",
        "/v1/openapi/device-information/device-id",
        {"errorCode": 40101, "msg": "Unauthorized"},
        "Unauthorized",
    )
    assert message == "TAUC error 40101: Unauthorized"
