from intelligence.officer_broker import OfficerKnowledgeBroker


def test_broker_keeps_officer_ownership_and_verified_state():
    reports = OfficerKnowledgeBroker().reports({
        "commander": "Test", "system": "Sol", "ship": "Anaconda",
        "biology": {"planets": 2}, "route": {"remaining_jumps": 3},
        "trade": {"product": "Silver"}, "mining": {"target": "Platinum"},
        "engineering": {"selected_plan": "fsd_range_g5"},
    })
    assert reports["MÍMIR"]["biology"]["planets"] == 2
    assert reports["HEIMDALL"]["route"]["remaining_jumps"] == 3
    assert reports["FREYJA"]["product"] == "Silver"
    assert reports["BROKK"]["target"] == "Platinum"
    assert reports["INGENIERÍA"]["selected_plan"] == "fsd_range_g5"


def test_broker_marks_missing_information_by_omission():
    reports = OfficerKnowledgeBroker().reports({"system": "Sol"})
    assert "route" not in reports["HEIMDALL"]
    assert reports["FREYJA"] == {}


def test_query_routes_only_to_relevant_officers():
    broker = OfficerKnowledgeBroker()
    context = broker.context(
        {"trade": {"product": "Silver"}, "mining": {"target": "Platinum"}},
        "¿Dónde puedo vender esta mercancía?",
    )
    assert '"FREYJA"' in context
    assert '"BROKK"' not in context
    assert broker.snapshot()["consulted_officers"] == ("ODIN", "FREYJA")


def test_station_compatibility_consults_navigation_and_trade():
    assert OfficerKnowledgeBroker.officers_for(
        "Buscá una estación cercana con plataforma grande"
    ) == ("ODIN", "HEIMDALL", "FREYJA")
