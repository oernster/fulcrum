"""Type conversions for the org draft, as a capability mixin.

OrgDraft mixes this in; splitting it out keeps each module within the
structural line limit. These are the operations behind the inspector's Type
dropdown: an item converts between team and unit in place, keeping its id and
letting an auto-generated name follow its type.
"""

from __future__ import annotations

from fulcrum.application.org_draft_nodes import (
    TEAM_TYPE,
    ContainerDraft,
    TeamDraft,
    can_nest,
    retitle_for_category,
)


class DraftConversions:
    """set_category and the team/unit conversions, mixed into OrgDraft."""

    def set_category(self, node_id: str, category: str) -> bool:
        """Change a unit's category, keeping an auto-generated name in step.

        Refused when the new tier would supersede the parent (a Company under
        a Division) or when the node is a team (teams convert instead).
        """
        node, _ = self._locate(node_id)
        if not isinstance(node, ContainerDraft):
            return False
        parent = self.parent_of(node_id)
        if parent is not None and not can_nest(category, parent.category):
            return False
        node.name = retitle_for_category(node.name, node.category, category)
        node.category = category
        return True

    def convert_to_container(self, node_id: str, category: str):
        """Turn a team into a unit of the given category; None when refused.

        The id and name carry over (an auto 'Team 3' becomes 'Division 3') and
        the owner becomes the lead. Dependencies the team carried are pruned,
        since only teams can depend on each other.
        """
        node, siblings = self._locate(node_id)
        if not isinstance(node, TeamDraft):
            return None
        parent = self.parent_of(node_id)
        if parent is not None and not can_nest(category, parent.category):
            return None
        container = ContainerDraft(
            id=node.id,
            category=category,
            name=retitle_for_category(node.name, TEAM_TYPE, category),
            lead=node.owner,
        )
        siblings[siblings.index(node)] = container
        self.dependencies = tuple(
            dep
            for dep in self.dependencies
            if node.id not in (dep.upstream, dep.downstream)
        )
        return container

    def convert_to_team(self, node_id: str):
        """Turn a childless unit into a team; None when it still holds items.

        The id and name carry over (an auto 'Division 3' becomes 'Team 3') and
        the lead becomes the owner.
        """
        node, siblings = self._locate(node_id)
        if not isinstance(node, ContainerDraft) or node.children:
            return None
        team = TeamDraft(
            id=node.id,
            name=retitle_for_category(node.name, node.category, TEAM_TYPE),
            owner=node.lead,
        )
        siblings[siblings.index(node)] = team
        return team

    def parent_of(self, node_id: str):
        """The container holding a node, or None at the top level.

        A node not at the top level always sits in some container's children,
        so the search below cannot fall through.
        """
        _, siblings = self._locate(node_id)
        if siblings is self.roots:
            return None
        return next(
            candidate
            for candidate in self._walk()
            if isinstance(candidate, ContainerDraft) and candidate.children is siblings
        )
