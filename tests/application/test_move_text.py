"""Tests for human-readable move descriptions."""

from fulcrum.application.move_text import (
    describe_move,
    describe_position_change,
    move_note,
)
from fulcrum.domain.models import AuthorityClaim, Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind


def _org():
    return OrgState(
        teams=(Team("a", "Alpha", False, 0.5), Team("b", "Bravo", False, 0.4)),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
    )


def test_describe_each_kind():
    org = _org()
    assert (
        describe_move(org, Move(MoveKind.DELEGATE_AUTHORITY, ("a",)))
        == "Delegate authority to Alpha"
    )
    assert (
        describe_move(org, Move(MoveKind.REALIGN_INCENTIVES, ("b",)))
        == "Realign incentives at Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
        == "Collapse Alpha + Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.STABILISE_INTERFACES))
        == "Stabilise all interfaces"
    )
    assert (
        describe_move(org, Move(MoveKind.ADD_APPROVAL_LAYER)) == "Add an approval layer"
    )


def test_describe_growth_kinds():
    org = _org()
    assert (
        describe_move(org, Move(MoveKind.SPLIT_TEAM, ("a",)))
        == "Split Alpha into two owners"
    )
    assert (
        describe_move(org, Move(MoveKind.ADD_TEAM, ("b",)))
        == "Add a new owner beside Bravo"
    )


def _claimed_org():
    return OrgState(
        teams=(Team("a", "Alpha", True, 0.0), Team("b", "Bravo", True, 0.0)),
        workload=1,
        domains=(Domain("unit", "Platform Unit"),),
        claims=(
            AuthorityClaim("b", "a"),
            AuthorityClaim("unit", "a"),
            AuthorityClaim("Head of QA", "a"),
        ),
    )


def test_describe_claim_kinds():
    org = _claimed_org()
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "a")))
        == "Resolve authority at Alpha in its favour"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "b")))
        == "Resolve authority at Alpha in favour of Bravo"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "unit")))
        == "Resolve authority at Alpha in favour of Platform Unit"
    )
    assert (
        describe_move(org, Move(MoveKind.RESOLVE_AUTHORITY, ("a", "Head of QA")))
        == "Resolve authority at Alpha in favour of Head of QA"
    )
    assert (
        describe_move(org, Move(MoveKind.DOWNGRADE_CLAIM, ("unit", "a")))
        == "Downgrade Platform Unit's claim on Alpha to consultation"
    )
    assert (
        describe_move(org, Move(MoveKind.IMPOSE_MATRIX_OVERLAY))
        == "Impose a matrix overlay"
    )


def test_move_note_covers_every_kind():
    for kind in MoveKind:
        assert move_note(kind)
    assert "not centralisation" in move_note(MoveKind.COLLAPSE_BOUNDARY)
    assert "blunder" in move_note(MoveKind.ADD_APPROVAL_LAYER)


def test_many_targets_are_capped_with_an_honest_count():
    """A wide move names a few teams and counts the rest, never a wall."""
    teams = tuple(Team(f"t{i}", f"T{i}", False, 0.0) for i in range(5))
    org = OrgState(teams=teams, workload=1)
    move = Move(MoveKind.DELEGATE_AUTHORITY, tuple(t.id for t in teams))
    assert (
        describe_move(org, move)
        == "Delegate authority to T0 + T1 + T2 and 2 more teams"
    )


def test_exactly_the_cap_is_named_in_full():
    teams = tuple(Team(f"t{i}", f"T{i}", False, 0.0) for i in range(3))
    org = OrgState(teams=teams, workload=1)
    move = Move(MoveKind.DELEGATE_AUTHORITY, tuple(t.id for t in teams))
    assert describe_move(org, move) == "Delegate authority to T0 + T1 + T2"


_UNITS = (Domain("u1", "Messaging"), Domain("u2", "Storage"))


def _base_position():
    return OrgState(
        teams=(
            Team("a", "Alpha", False, 0.5, domain_id="u1"),
            Team("b", "Bravo", True, 0.4, domain_id="u2"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        domains=_UNITS,
    )


def test_change_line_locates_authority_and_counts_claims_and_teams():
    before = _base_position()
    after = OrgState(
        teams=(
            Team("a", "Alpha", True, 0.5, domain_id="u1"),
            Team("b", "Bravo", False, 0.4, domain_id="u2"),
            Team("c", "Charlie", True, 0.0),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        domains=_UNITS,
        claims=(AuthorityClaim("Head of QA", "a"),),
    )
    line = describe_position_change(before, after)
    assert "now deciding locally: 1 team in Messaging" in line
    assert "no longer deciding locally: 1 team in Storage" in line
    assert "teams 2 → 3" in line
    assert "standing claims 0 → 1" in line


def test_change_line_names_several_units_and_the_unassigned():
    before = OrgState(
        teams=(
            Team("a", "Alpha", False, domain_id="u1"),
            Team("b", "Bravo", False, domain_id="u2"),
            Team("c", "Charlie", False),
        ),
        workload=1,
        domains=_UNITS,
    )
    after = OrgState(
        teams=(
            Team("a", "Alpha", True, domain_id="u1"),
            Team("b", "Bravo", True, domain_id="u2"),
            Team("c", "Charlie", True),
        ),
        workload=1,
        domains=_UNITS,
    )
    line = describe_position_change(before, after)
    assert (
        "now deciding locally: 3 teams in Messaging, Storage and unassigned teams"
        in line
    )


def test_change_line_counts_units_past_the_naming_cap():
    domains = tuple(Domain(f"u{i}", f"Unit {i}") for i in range(5))
    before = OrgState(
        teams=tuple(Team(f"t{i}", f"T{i}", False, domain_id=f"u{i}") for i in range(5)),
        workload=1,
        domains=domains,
    )
    after = OrgState(
        teams=tuple(Team(f"t{i}", f"T{i}", True, domain_id=f"u{i}") for i in range(5)),
        workload=1,
        domains=domains,
    )
    line = describe_position_change(before, after)
    assert "5 teams in Unit 0, Unit 1, Unit 2 and 2 more units" in line


def test_change_line_states_dependency_count_and_delay():
    before = _base_position()
    fewer = OrgState(teams=before.teams, dependencies=(), workload=4, domains=_UNITS)
    assert "dependencies 1 → 0" in describe_position_change(before, fewer)
    slower = OrgState(
        teams=before.teams,
        dependencies=(Dependency("a", "b", 9),),
        workload=4,
        domains=_UNITS,
    )
    assert "total propagation delay 3 → 9" in describe_position_change(before, slower)


def test_change_line_locates_skew_realignment():
    before = _base_position()
    after = OrgState(
        teams=(
            Team("a", "Alpha", False, 0.1, domain_id="u1"),
            Team("b", "Bravo", True, 0.4, domain_id="u2"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        domains=_UNITS,
    )
    line = describe_position_change(before, after)
    assert line == ("incentive skew realigned at 1 team in Messaging, mean 0.50 → 0.10")


def test_change_line_for_identical_positions():
    before = _base_position()
    assert describe_position_change(before, before) == "no structural field changed"
