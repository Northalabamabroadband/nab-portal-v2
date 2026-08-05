from app.modules.uisp.client import extract_records


def test_extract_records_list() -> None:
    payload = [{"id": 1}, {"id": 2}]
    assert extract_records(payload) == payload


def test_extract_records_wrapped() -> None:
    payload = {"items": [{"id": 1}]}
    assert extract_records(payload) == [{"id": 1}]


def test_extract_records_invalid() -> None:
    assert extract_records({"value": "not-a-list"}) == []
