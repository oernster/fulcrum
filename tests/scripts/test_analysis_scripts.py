"""Smoke tests for the three analysis scripts at the repository root.

These are development instruments rather than shipped surface, so they sit
outside the coverage gate. They are not outside the suite: `calibrate.py` is
the tool that says whether the scoring model still lands its calibration
cases inside their expected bands, and a silently broken calibrator reports
success. Each test asserts the script runs, exits zero and emits the shape
its reader depends on.

`generate_matrixed_enterprise.py` is checked differently: its committed
output is compared against a fresh build, which proves both that the
generator still works and that the calibration case in `examples/` is
reproducible from the script alone. Nothing here writes to the repository.
"""

import json

import calibrate
import generate_matrixed_enterprise as generator
import sensitivity


def test_every_calibration_case_lands_inside_its_expected_band(capsys):
    exit_code = calibrate.run()
    output = capsys.readouterr().out
    assert exit_code == 0, output
    assert "Every calibration case sits inside its expected band." in output
    assert "case" in output
    assert "PASS" in output
    assert "MISS" not in output


def test_the_calibration_runner_reports_one_row_per_case(capsys):
    calibrate.run()
    output = capsys.readouterr().out
    cases = sorted(
        path
        for path in calibrate.CALIBRATION_DIR.glob("*.json")
        if path.name != calibrate.TEMPLATE_NAME
    )
    assert cases
    for path in cases:
        label = json.loads(path.read_text(encoding="utf-8"))["calibration"]["label"]
        assert label in output


def test_the_sensitivity_sweep_holds_every_conclusion(capsys):
    exit_code = sensitivity.main()
    output = capsys.readouterr().out
    assert exit_code == 0, output
    assert "All five qualitative conclusions survive every perturbation." in output
    assert "Baseline scores (default coefficients)" in output
    assert f"{sensitivity.JOINT_DRAWS} draws" in output
    assert "all five together" in output
    for label in (label for _, label in sensitivity.CONCLUSIONS):
        assert label in output


def test_the_sweep_covers_every_tunable_coefficient(capsys):
    sensitivity.main()
    output = capsys.readouterr().out
    swept = sensitivity.INDEPENDENT_COEFFICIENTS + sensitivity.COMPOSITE_WEIGHTS
    assert swept
    for name in swept:
        assert name in output


def test_the_matrixed_enterprise_case_is_reproducible_from_the_script():
    built = generator.build()
    committed = json.loads(generator.OUTPUT_PATH.read_text(encoding="utf-8"))
    assert built == committed


def test_the_generated_case_hits_its_target_population():
    built = generator.build()
    people = sum(team["headcount"] for team in built["teams"])
    assert people == generator.TARGET_PEOPLE
    assert built["calibration"]["label"].startswith("Matrixed enterprise")
    assert built["origin"] == "imported"
    assert built["claims"]
    assert built["dependencies"]
