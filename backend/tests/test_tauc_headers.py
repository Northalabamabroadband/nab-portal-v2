from app.modules.tauc.client import TAUCClient


def test_tauc_signing_headers_have_timestamp() -> None:
    client = TAUCClient()
    headers = client.signing_headers(
        method="POST",
        path="/test",
        body={"sn": "ABC123"},
    )

    assert "X-Timestamp" in headers
    assert headers["Content-Type"] == "application/json"


def test_mac_normalization_shape() -> None:
    mac = "74:FE:CE:3A:70:91"
    normalized = mac.replace(":", "").replace("-", "").upper()
    assert normalized == "74FECE3A7091"
