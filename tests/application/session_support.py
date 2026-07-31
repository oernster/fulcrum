"""Shared builders for the game-session test files."""

from fulcrum.application.dto import MoveValuation
from fulcrum.domain.models import Dependency, Domain, OrgState, Team
from fulcrum.domain.simulation import MoveClassification, StructuralScore

_SCORE = 50.0
_AFTER = 55.0


class FakeSimulator:
    def score(self, org):
        return StructuralScore(_SCORE, 0.0, 0.0, 0.0)

    def valuate_moves(self, org, moves):
        return tuple(
            MoveValuation(m, _SCORE, _AFTER, MoveClassification.GOOD) for m in moves
        )


def flat_org():
    return OrgState(
        teams=(Team("a", "A", True, 0.0), Team("b", "B", False, 0.5)),
        dependencies=(Dependency("a", "b", 3),),
        workload=2,
    )


def nested_org():
    return OrgState(
        teams=(
            Team("a", "A", False, 0.5, domain_id="d1"),
            Team("b", "B", False, 0.5, domain_id="d1"),
            Team("c", "C", True, 0.0, domain_id="d2"),
        ),
        dependencies=(Dependency("a", "b", 2), Dependency("b", "c", 2)),
        workload=2,
        domains=(
            Domain("root", "Org"),
            Domain("d1", "Dept One", parent_id="root"),
            Domain("d2", "Dept Two", parent_id="root"),
        ),
    )
