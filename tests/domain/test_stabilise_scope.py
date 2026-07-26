"""Tests for frame-scoped stabilise: thin only the edges the frame prices."""

import pytest

from fulcrum.domain.errors import UnknownTeamError
from fulcrum.domain.hierarchy import TOP_LEVEL_FOCUS, translate_focused_move
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.moves import Move, MoveKind, apply_move


def _t(team_id, domain_id=None):
    return Team(team_id, team_id.upper(), True, 0.0, domain_id=domain_id)


def _hierarchical():
    return OrgState(
        teams=(
            _t("a1", "d1"),
            _t("a2", "d1"),
            _t("b1", "d2"),
        ),
        dependencies=(
            Dependency("a1", "a2", 10),
            Dependency("a2", "b1", 10),
            Dependency("d1", "d2", 10),
        ),
        workload=2,
        domains=(Domain("d1", "One"), Domain("d2", "Two")),
    )


def test_team_targets_thin_only_edges_between_them():
    org = _hierarchical()
    after = apply_move(org, Move(MoveKind.STABILISE_INTERFACES, ("a1", "a2")))
    delays = {
        (d.upstream, d.downstream): d.propagation_delay for d in after.dependencies
    }
    assert delays[("a1", "a2")] == 4
    assert delays[("a2", "b1")] == 10
    assert delays[("d1", "d2")] == 10


def test_unit_targets_thin_cross_unit_edges_including_unit_level_ones():
    org = _hierarchical()
    after = apply_move(org, Move(MoveKind.STABILISE_INTERFACES, ("d1", "d2")))
    delays = {
        (d.upstream, d.downstream): d.propagation_delay for d in after.dependencies
    }
    # Internal to one unit: untouched. Crossing units, team-level or
    # unit-level: thinned, exactly the edges the top frame prices.
    assert delays[("a1", "a2")] == 10
    assert delays[("a2", "b1")] == 4
    assert delays[("d1", "d2")] == 4


def test_untargeted_stabilise_keeps_the_legacy_thin_everything_meaning():
    org = _hierarchical()
    after = apply_move(org, Move(MoveKind.STABILISE_INTERFACES))
    assert all(d.propagation_delay == 4 for d in after.dependencies)


def test_stabilise_rejects_an_unknown_node():
    with pytest.raises(UnknownTeamError):
        apply_move(_hierarchical(), Move(MoveKind.STABILISE_INTERFACES, ("ghost",)))


def test_translate_leaves_scoped_stabilise_untouched():
    org = _hierarchical()
    move = Move(MoveKind.STABILISE_INTERFACES, ("d1", "d2"))
    assert translate_focused_move(org, TOP_LEVEL_FOCUS, move) is move
