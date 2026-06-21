"""Tests for off-thread scope analysis."""

from fulcrum.application.game_session import MAX_PLAYABLE_TEAMS, enumerate_moves
from fulcrum.application.scope_analysis import active_org, analyze_scope
from fulcrum.application.simulator import DeterministicSimulator
from fulcrum.domain.models import Dependency, Domain, OrgState, Team

_SIM = DeterministicSimulator()


def _org():
    return OrgState(
        teams=(
            Team("a", "A", True, 0.0, domain_id="d1"),
            Team("b", "B", False, 0.5, domain_id="d1"),
            Team("c", "C", True, 0.0, domain_id="d2"),
        ),
        dependencies=(Dependency("a", "b", 3),),
        workload=2,
        domains=(Domain("d1", "Platform"), Domain("d2", "Data")),
    )


def test_active_org_is_the_whole_org_without_focus():
    org = _org()
    assert active_org(org, None) is org


def test_active_org_is_the_focused_section():
    active = active_org(_org(), "d1")
    assert {t.id for t in active.teams} == {"a", "b"}


def test_analyze_whole_small_org_is_playable():
    org = _org()
    result = analyze_scope(org, None, _SIM)
    assert result.playable is True
    assert result.score == _SIM.score(org).value
    assert len(result.signals) == 4
    assert len(result.valuations) == len(enumerate_moves(org))


def test_analyze_focused_section_scores_only_that_section():
    org = _org()
    result = analyze_scope(org, "d1", _SIM)
    assert result.playable is True
    assert len(result.valuations) == len(enumerate_moves(active_org(org, "d1")))


def test_analyze_large_scope_is_not_playable():
    teams = tuple(
        Team(f"t{i}", f"T{i}", True, 0.0) for i in range(MAX_PLAYABLE_TEAMS + 1)
    )
    result = analyze_scope(OrgState(teams=teams, workload=1), None, _SIM)
    assert result.playable is False
    assert result.score == 0.0
    assert result.signals == ()
    assert result.valuations == ()
