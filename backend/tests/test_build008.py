from app.modules.incidents.service import dispatch_resource_id, incident_marker


def test_incident_marker_is_normalized() -> None:
    assert incident_marker("Saturn Campus") == "[incident:saturn-campus]"


def test_dispatch_resource_ids_are_stable_and_distinct() -> None:
    first_ticket = dispatch_resource_id("saturn-campus", "ticket")
    retry_ticket = dispatch_resource_id("saturn-campus", "ticket")
    workorder = dispatch_resource_id("saturn-campus", "workorder")

    assert first_ticket == retry_ticket
    assert first_ticket != workorder
