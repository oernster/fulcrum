"""The move vocabulary and the helpers move handlers share.

Splitting the vocabulary from the handlers keeps each module within the
structural line limit and lets the claim moves live in their own module
without a circular import: handlers import this, never each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fulcrum.domain.models import Dependency, OrgState


class MoveKind(str, Enum):
    """The structural interventions a player can make."""

    ADD_APPROVAL_LAYER = "add_approval_layer"
    STABILISE_INTERFACES = "stabilise_interfaces"
    DELEGATE_AUTHORITY = "delegate_authority"
    REALIGN_INCENTIVES = "realign_incentives"
    COLLAPSE_BOUNDARY = "collapse_boundary"
    SPLIT_TEAM = "split_team"
    ADD_TEAM = "add_team"
    RESOLVE_AUTHORITY = "resolve_authority"
    DOWNGRADE_CLAIM = "downgrade_claim"
    IMPOSE_MATRIX_OVERLAY = "impose_matrix_overlay"


@dataclass(frozen=True, slots=True)
class Move:
    """A structural move: a kind plus the team ids it acts on."""

    kind: MoveKind
    targets: tuple[str, ...] = ()
    label: str = ""

    def display_label(self) -> str:
        return self.label or self.kind.value.replace("_", " ")


def dep_sort_key(dep: Dependency) -> tuple[str, str, int]:
    """A deterministic ordering for dependency tuples."""
    return (dep.upstream, dep.downstream, dep.propagation_delay)


def repoint(dep: Dependency, old_id: str, new_id: str) -> Dependency:
    """The same dependency with one endpoint renamed."""
    upstream = new_id if dep.upstream == old_id else dep.upstream
    downstream = new_id if dep.downstream == old_id else dep.downstream
    return Dependency(upstream, downstream, dep.propagation_delay)


def unique_team_id(org: OrgState, base: str) -> str:
    """base, or base_2, base_3 ... whichever is first unused as a team id."""
    existing = set(org.team_ids)
    candidate = base
    index = 1
    while candidate in existing:
        index += 1
        candidate = f"{base}_{index}"
    return candidate


def unique_prefixed_id(org: OrgState, prefix: str) -> str:
    """prefix_1, prefix_2 ... whichever is first unused as a team id."""
    existing = set(org.team_ids)
    index = 1
    candidate = f"{prefix}_{index}"
    while candidate in existing:
        index += 1
        candidate = f"{prefix}_{index}"
    return candidate
