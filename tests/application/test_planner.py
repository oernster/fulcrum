"""Tests for the improvement planner (the guide / cheat feature)."""

from fulcrum.application.planner import Guide, ImprovementPlanner
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, OrgState, Team
from fulcrum.domain.moves import MoveKind


def _broken():
    return OrgState(
        teams=(
            Team("a", "A", False, 0.5),
            Team("b", "B", False, 0.5),
            Team("c", "C", False, 0.4),
        ),
        dependencies=(
            Dependency("a", "b", 5),
            Dependency("b", "c", 5),
            Dependency("a", "c", 5),
        ),
        workload=8,
    )


def _healthy():
    return OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", True, 0.0)), workload=1
    )


def test_plan_improves_a_broken_org():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(_broken())
    assert isinstance(guide, Guide)
    assert guide.steps
    assert guide.final_score > guide.start_score
    scores = [guide.start_score] + [step.score_after for step in guide.steps]
    assert scores == sorted(scores)


def test_plan_stops_when_nothing_improves():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(_healthy())
    assert guide.steps == ()
    assert guide.final_score == guide.start_score


def test_plan_respects_max_steps():
    guide = ImprovementPlanner(DeterministicSimulator(), max_steps=1).plan(_broken())
    assert len(guide.steps) == 1


def _overloaded_hub():
    leaves = tuple(Team(f"leaf_{i}", f"Leaf {i}", True, 0.0) for i in range(1, 5))
    hub = Team("hub", "Hub", True, 0.0)
    deps = tuple(Dependency("hub", f"leaf_{i}", 0) for i in range(1, 5))
    return OrgState(teams=(hub,) + leaves, dependencies=deps, workload=9)


def test_plan_allow_growth_selects_a_growth_move():
    guide = ImprovementPlanner(DeterministicSimulator(), allow_growth=True).plan(
        _overloaded_hub()
    )
    kinds = {step.move.kind for step in guide.steps}
    assert MoveKind.ADD_TEAM in kinds
    assert guide.final_score > guide.start_score
    scores = [guide.start_score] + [step.score_after for step in guide.steps]
    assert scores == sorted(scores)


def test_plan_without_growth_offers_no_growth_moves():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(_overloaded_hub())
    kinds = {step.move.kind for step in guide.steps}
    assert MoveKind.ADD_TEAM not in kinds
    assert MoveKind.SPLIT_TEAM not in kinds


def test_plan_restricts_to_allowed_move_kinds():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(
        _broken(), allowed_kinds=(MoveKind.DELEGATE_AUTHORITY,)
    )
    assert guide.steps
    assert {step.move.kind for step in guide.steps} == {MoveKind.DELEGATE_AUTHORITY}


def test_plan_with_no_allowed_kinds_yields_no_steps():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(
        _broken(), allowed_kinds=()
    )
    assert guide.steps == ()


def test_plan_labels_each_step_with_a_description():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(_broken())
    assert guide.steps
    assert all(step.move.label for step in guide.steps)


def test_plan_steps_carry_the_org_and_score_before_each_move():
    guide = ImprovementPlanner(DeterministicSimulator()).plan(_broken())
    assert guide.steps
    assert guide.steps[0].score_before == guide.start_score
    for earlier, later in zip(guide.steps, guide.steps[1:]):
        assert later.score_before == earlier.score_after
    assert all(isinstance(step.org_before, OrgState) for step in guide.steps)
