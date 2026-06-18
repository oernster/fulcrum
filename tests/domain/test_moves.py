"""Tests for the structural move transformations."""

import pytest

from fulcrum.domain.errors import InvalidMoveError, UnknownTeamError
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move


def _t(team_id, authority=True, skew=0.0):
    return Team(
        id=team_id,
        name=team_id.upper(),
        has_local_authority=authority,
        incentive_skew=skew,
    )


def _org():
    return OrgState(
        teams=(_t("a", False, 0.4), _t("b", False, 0.6), _t("c", True, 0.2)),
        dependencies=(
            Dependency("a", "b", 4),
            Dependency("b", "c", 4),
            Dependency("a", "c", 4),
        ),
        workload=6,
    )


def test_display_label_default_and_custom():
    plain = Move(MoveKind.STABILISE_INTERFACES)
    assert plain.display_label() == "stabilise interfaces"
    assert Move(MoveKind.STABILISE_INTERFACES, label="Tidy").display_label() == "Tidy"


def test_apply_move_unknown_target():
    with pytest.raises(UnknownTeamError):
        apply_move(_org(), Move(MoveKind.DELEGATE_AUTHORITY, ("z",)))


def test_add_approval_layer_adds_gate_and_deps():
    org = _org()
    out = apply_move(org, Move(MoveKind.ADD_APPROVAL_LAYER))
    assert len(out.teams) == len(org.teams) + 1
    assert out.teams[-1].has_local_authority is False
    assert len(out.dependencies) == len(org.dependencies) + len(org.teams)


def test_add_approval_layer_unique_id_on_collision():
    org = OrgState(teams=(_t("approval_1"), _t("b")), workload=2)
    out = apply_move(org, Move(MoveKind.ADD_APPROVAL_LAYER))
    assert set(out.team_ids) - set(org.team_ids) == {"approval_2"}


def test_stabilise_interfaces_reduces_delay():
    out = apply_move(_org(), Move(MoveKind.STABILISE_INTERFACES))
    assert all(d.propagation_delay < 4 for d in out.dependencies)


def test_delegate_authority_sets_flag_and_requires_target():
    out = apply_move(_org(), Move(MoveKind.DELEGATE_AUTHORITY, ("a",)))
    assert out.team("a").has_local_authority is True
    with pytest.raises(InvalidMoveError):
        apply_move(_org(), Move(MoveKind.DELEGATE_AUTHORITY, ()))


def test_realign_incentives_reduces_skew_and_requires_target():
    out = apply_move(_org(), Move(MoveKind.REALIGN_INCENTIVES, ("b",)))
    assert out.team("b").incentive_skew < 0.6
    with pytest.raises(InvalidMoveError):
        apply_move(_org(), Move(MoveKind.REALIGN_INCENTIVES, ()))


def test_collapse_boundary_merges_and_requires_two():
    out = apply_move(_org(), Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    assert not out.has_team("b")
    assert out.team("a").has_local_authority is False
    with pytest.raises(InvalidMoveError):
        apply_move(_org(), Move(MoveKind.COLLAPSE_BOUNDARY, ("a",)))


def test_collapse_boundary_remaps_dedup_and_drops_self_loops():
    org = OrgState(
        teams=(_t("a", True), _t("b", False), _t("c", True)),
        dependencies=(
            Dependency("a", "b", 1),
            Dependency("b", "a", 1),
            Dependency("a", "c", 1),
            Dependency("b", "c", 1),
        ),
        workload=2,
    )
    out = apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    pairs = sorted((d.upstream, d.downstream) for d in out.dependencies)
    assert pairs == [("a", "c")]
    assert out.team("a").has_local_authority is True


def test_split_team_shares_dependencies_with_an_inheriting_sibling():
    org = OrgState(
        teams=(_t("a"), _t("b", True, 0.3), _t("c"), _t("d")),
        dependencies=(
            Dependency("a", "b", 2),
            Dependency("b", "c", 5),
            Dependency("d", "b", 7),
        ),
        workload=4,
    )
    out = apply_move(org, Move(MoveKind.SPLIT_TEAM, ("b",)))
    assert (set(out.team_ids) - set(org.team_ids)) == {"b_b"}
    sibling = out.team("b_b")
    assert sibling.has_local_authority is True
    assert sibling.incentive_skew == 0.3
    pairs = sorted((d.upstream, d.downstream) for d in out.dependencies)
    assert pairs == [("a", "b"), ("b_b", "c"), ("d", "b_b")]
    moved = next(d for d in out.dependencies if d.downstream == "b_b")
    assert moved.upstream == "d"
    assert moved.propagation_delay == 7
    assert not any({d.upstream, d.downstream} == {"b", "b_b"} for d in out.dependencies)


def test_split_team_makes_a_unique_sibling_id():
    org = OrgState(
        teams=(_t("x"), _t("x_b"), _t("y"), _t("z")),
        dependencies=(Dependency("x", "y", 1), Dependency("x", "z", 1)),
        workload=2,
    )
    out = apply_move(org, Move(MoveKind.SPLIT_TEAM, ("x",)))
    assert (set(out.team_ids) - set(org.team_ids)) == {"x_b_2"}


def test_split_team_requires_one_target():
    with pytest.raises(InvalidMoveError):
        apply_move(_org(), Move(MoveKind.SPLIT_TEAM, ()))


def test_add_team_hands_one_dependency_to_a_new_owner():
    org = OrgState(
        teams=(_t("a"), _t("b", True, 0.5), _t("c")),
        dependencies=(Dependency("a", "b", 3), Dependency("b", "c", 4)),
        workload=4,
    )
    out = apply_move(org, Move(MoveKind.ADD_TEAM, ("b",)))
    assert (set(out.team_ids) - set(org.team_ids)) == {"b_owner"}
    owner = out.team("b_owner")
    assert owner.has_local_authority is True
    assert owner.incentive_skew == 0.0
    pairs = sorted((d.upstream, d.downstream) for d in out.dependencies)
    assert pairs == [("a", "b_owner"), ("b", "c")]


def test_add_team_requires_one_target():
    with pytest.raises(InvalidMoveError):
        apply_move(_org(), Move(MoveKind.ADD_TEAM, ()))


def test_collapse_sums_team_size():
    org = OrgState(
        teams=(_t("a", True), _t("b", True)),
        dependencies=(Dependency("a", "b", 1),),
        workload=2,
    )
    out = apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    assert out.team("a").size == 2


def test_split_divides_team_size():
    org = OrgState(
        teams=(Team("a", "A", True, 0.0, size=4), _t("b", True)),
        dependencies=(Dependency("a", "b", 1), Dependency("b", "a", 1)),
        workload=2,
    )
    out = apply_move(org, Move(MoveKind.SPLIT_TEAM, ("a",)))
    assert out.team("a").size == 2
    assert out.team("a_b").size == 2


def _domained_org():
    return OrgState(
        teams=(
            Team("a", "A", False, 0.4, domain_id="d1", owner="Ada"),
            Team("b", "B", True, 0.2, domain_id="d1"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=4,
        domains=(Domain("d1", "Domain One", lead="Dana"),),
    )


def test_every_move_preserves_domains_and_domain_id():
    org = _domained_org()
    delegated = apply_move(org, Move(MoveKind.DELEGATE_AUTHORITY, ("a",)))
    assert delegated.domains == org.domains
    assert delegated.team("a").domain_id == "d1"

    realigned = apply_move(org, Move(MoveKind.REALIGN_INCENTIVES, ("a",)))
    assert realigned.domains == org.domains
    assert realigned.team("a").domain_id == "d1"

    stabilised = apply_move(org, Move(MoveKind.STABILISE_INTERFACES))
    assert stabilised.domains == org.domains

    gated = apply_move(org, Move(MoveKind.ADD_APPROVAL_LAYER))
    assert gated.domains == org.domains

    collapsed = apply_move(org, Move(MoveKind.COLLAPSE_BOUNDARY, ("a", "b")))
    assert collapsed.domains == org.domains
    assert collapsed.team("a").domain_id == "d1"
    assert collapsed.team("a").owner == "Ada"

    split = apply_move(org, Move(MoveKind.SPLIT_TEAM, ("a",)))
    assert split.domains == org.domains
    assert split.team("a_b").domain_id == "d1"
    assert split.team("a_b").owner == "Ada"

    grown = apply_move(org, Move(MoveKind.ADD_TEAM, ("a",)))
    assert grown.domains == org.domains
    assert grown.team("a_owner").domain_id == "d1"
