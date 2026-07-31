"""Tests for the file-backed example library behind the File menu."""

import json

from fulcrum.domain.models import Domain, OrgState, Origin, Team
from fulcrum.infrastructure.example_library import FileExampleLibrary
from fulcrum.infrastructure.json_serialization import org_to_dict


def _org() -> OrgState:
    return OrgState(
        teams=(
            Team("a", "A", True, domain_id="company", headcount=6),
            Team("b", "B", False, domain_id="company", headcount=6),
        ),
        workload=3,
        origin=Origin.IMPORTED,
        domains=(Domain("company", "Company"),),
    )


def _write_case(directory, name, label="Case", note="what happened"):
    data = org_to_dict(_org())
    data["calibration"] = {
        "label": label,
        "expected_min": 0,
        "expected_max": 100,
        "note": note,
    }
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_lists_cases_sorted_by_label_with_notes(tmp_path):
    _write_case(tmp_path, "zeta.json", label="Zeta org", note="ended badly")
    _write_case(tmp_path, "alpha.json", label="Alpha org", note="went well")
    library = FileExampleLibrary(tmp_path)
    summaries = library.examples()
    assert [s.label for s in summaries] == ["Alpha org", "Zeta org"]
    assert summaries[0].note == "went well"
    assert summaries[0].key.endswith("alpha.json")


def test_skips_template_broken_json_and_unannotated_files(tmp_path):
    _write_case(tmp_path, "good.json")
    _write_case(tmp_path, "TEMPLATE.json", label="Template")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "plain.json").write_text(
        json.dumps(org_to_dict(_org())), encoding="utf-8"
    )
    (tmp_path / "odd.json").write_text(
        json.dumps({"calibration": "not a dict"}), encoding="utf-8"
    )
    library = FileExampleLibrary(tmp_path)
    assert [s.label for s in library.examples()] == ["Case"]


def test_missing_directory_yields_no_examples(tmp_path):
    assert FileExampleLibrary(None).examples() == ()
    assert FileExampleLibrary(tmp_path / "absent").examples() == ()


def test_load_round_trips_the_org(tmp_path):
    _write_case(tmp_path, "case.json")
    library = FileExampleLibrary(tmp_path)
    (summary,) = library.examples()
    org = library.load(summary.key)
    assert org == _org()


def test_shipped_calibration_cases_all_list_and_load():
    """The real directory the app bundles stays loadable end to end."""
    from fulcrum.shared.resources import find_examples_dir

    directory = find_examples_dir()
    assert directory is not None
    library = FileExampleLibrary(directory)
    summaries = library.examples()
    assert len(summaries) >= 3
    for summary in summaries:
        assert library.load(summary.key).teams
