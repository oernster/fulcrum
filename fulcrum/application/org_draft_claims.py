"""Authority-claim operations for the org draft, as a capability mixin.

OrgDraft mixes this in; splitting it out keeps each module within the
structural line limit. Claims are the editor's representation of matrix and
dual-reporting structure: another node asserting the right to decide for a
team. A team's own authority stays the Ships-without-asking flag, never a
self-claim, so there is one source of truth for it.
"""

from __future__ import annotations

from fulcrum.application.dto import ClaimSpec
from fulcrum.application.org_draft_nodes import TeamDraft


class DraftClaims:
    """can_claim, add_claim, remove_claim and the claim queries."""

    def can_claim(self, claimant_id: str, subject_id: str) -> bool:
        """Whether a claim on a team's decisions is legal.

        The subject must be a team (a decision class lives at a leaf) and the
        claimant a different, non-empty actor. The claimant is deliberately
        not required to be a modelled node, matching the domain: an imported
        chapter or role can contest a team without sitting on the delivery
        graph. Duplication is not a legality question: the claim table edits
        live rows against the stored claims, so add_claim and the table's own
        harvest deduplicate instead.
        """
        if not claimant_id or claimant_id == subject_id:
            return False
        return isinstance(self.find(subject_id), TeamDraft)

    def add_claim(self, claimant_id: str, subject_id: str) -> bool:
        """Record a claim when legal and new; report whether it was added."""
        if not self.can_claim(claimant_id, subject_id):
            return False
        if any(
            c.claimant == claimant_id and c.subject == subject_id for c in self.claims
        ):
            return False
        self.claims = self.claims + (ClaimSpec(claimant_id, subject_id),)
        return True

    def remove_claim(self, claimant_id: str, subject_id: str) -> None:
        """Drop a claim if present."""
        self.claims = tuple(
            c
            for c in self.claims
            if not (c.claimant == claimant_id and c.subject == subject_id)
        )

    def claims_on(self, subject_id: str) -> tuple[ClaimSpec, ...]:
        """The claims recorded against one team, in insertion order."""
        return tuple(c for c in self.claims if c.subject == subject_id)

    def claimant_options(self, subject_id: str) -> tuple[tuple[str, str], ...]:
        """(id, label) for every node that could legally claim the subject."""
        return tuple(
            (ident, label)
            for ident, label in self.dependency_options()
            if self.can_claim(ident, subject_id)
        )
