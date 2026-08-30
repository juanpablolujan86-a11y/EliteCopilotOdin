from engineering.planner import (
    ENGINEERING_PLANS,
    EngineeringTracker,
    normalize_engineering_objective,
    resolve_engineer_name,
)


def tracker(tmp_path):
    return EngineeringTracker(tmp_path / "engineering" / "selected_plan.json")


def test_engineer_progress_and_unknown_engineer_are_preserved(tmp_path):
    subject = tracker(tmp_path)
    subject.handle({"event": "EngineerProgress", "Engineers": [
        {"Engineer": "Felicity Farseer", "Progress": "Unlocked", "Rank": 5,
         "RankProgress": 100},
        {"Engineer": "Future Engineer", "Progress": "Invited", "Rank": 0},
    ]})

    snapshot = subject.snapshot()
    assert snapshot["engineers"]["Felicity Farseer"]["status"] == "Unlocked"
    assert snapshot["engineers"]["Felicity Farseer"]["system"] == "Deciat"
    assert snapshot["engineers"]["Future Engineer"]["status"] == "Invited"


def test_materials_make_selected_plan_ready_and_persist(tmp_path):
    subject = tracker(tmp_path)
    plan_key = "fsd_range_g5"
    plan = ENGINEERING_PLANS[plan_key]
    raw, manufactured, encoded = [], [], []
    buckets = (raw, manufactured, encoded)
    for index, (name, (_label, required)) in enumerate(plan["materials"].items()):
        buckets[index].append({"Name": name, "Count": required})
    subject.handle({"event": "Materials", "Raw": raw,
                    "Manufactured": manufactured, "Encoded": encoded})

    assert subject.select_plan(plan_key)
    assert subject.snapshot()["plans"][plan_key]["complete"] is True
    assert tracker(tmp_path).selected_plan == plan_key


def test_engineer_craft_consumes_materials_and_records_craft(tmp_path):
    subject = tracker(tmp_path)
    subject.handle({"event": "Materials", "Raw": [{"Name": "arsenic", "Count": 3}],
                    "Manufactured": [], "Encoded": []})
    subject.handle({"event": "EngineerCraft", "Engineer": "Felicity Farseer",
                    "BlueprintName": "FSD_LongRange", "Level": 5,
                    "Ingredients": [{"Name": "arsenic", "Count": 1}]})

    snapshot = subject.snapshot()
    assert subject.materials["arsenic"] == 2
    assert snapshot["last_craft"]["blueprint"] == "FSD_LongRange"


def test_loadout_lists_engineered_modules(tmp_path):
    subject = tracker(tmp_path)
    subject.handle({"event": "Loadout", "Modules": [
        {"Slot": "FrameShiftDrive", "Item": "Int_Hyperdrive_Size5_Class5",
         "Engineering": {"Engineer": "Felicity Farseer",
                         "BlueprintName": "FSD_LongRange", "Level": 5,
                         "ExperimentalEffect_Localised": "Gestor de masa"}},
        {"Slot": "CargoHatch", "Item": "ModularCargoBayDoor"},
    ]})

    modules = subject.snapshot()["modules"]
    assert len(modules) == 1
    assert modules[0]["grade"] == 5
    assert modules[0]["experimental"] == "Gestor de masa"


def test_voice_alias_resolves_marco_qwent_without_guessing_an_unknown_name():
    assert resolve_engineer_name("Marco Cuenta") == "Marco Qwent"
    assert (
        normalize_engineering_objective("quiero desbloquear el ingeniero Marco Cuenta")
        == "desbloquear al ingeniero Marco Qwent"
    )
    assert resolve_engineer_name("nombre completamente desconocido") is None


def test_confirmed_voice_alias_persists_between_sessions(tmp_path):
    first = tracker(tmp_path)
    assert first.learn_voice_alias("Marco Cuentita", "Marco Qwent")

    restored = tracker(tmp_path)
    assert restored.resolve_engineer("Marco Cuentita") == "Marco Qwent"
