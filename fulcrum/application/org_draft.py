"""The editable draft of an organisation: the model behind the org editor.

The editor UI is a thin view over this draft. Every structural operation (add,
remove, move, duplicate), every query (rollups, warnings, acceptance) and the
placement rules live here, so the behaviour is tested under the coverage gate
and the editor is a pure function of the model. The node types live in
org_draft_nodes; blueprint serialisation and the type conversions are mixed in
from org_draft_io and org_draft_convert.
"""

from __future__ import annotations

from fulcrum.application.dto import DependencySpec
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft_convert import DraftConversions
from fulcrum.application.org_draft_io import DraftSerialisation
from fulcrum.application.org_draft_nodes import (
    ContainerDraft,
    DraftWarning,
    RemovalSummary,
    TeamDraft,
    can_nest,
    default_category_for_depth,
    iter_nodes,
    sequence_token,
    subtree,
    teams_beneath,
)

DEFAULT_WORKLOAD = 6

_TEAM_PREFIX = "team"
_CONTAINER_PREFIX = "domain"
_DUPLICATE_SUFFIX = " copy"


class OrgDraft(DraftConversions, DraftSerialisation):
    """A mutable org structure with the operations the editor exposes."""

    def __init__(self, names: NamePicker, workload: int = DEFAULT_WORKLOAD) -> None:
        self.roots: list = []
        self.dependencies: tuple[DependencySpec, ...] = ()
        self.workload = workload
        self._names = names
        self._seq = 0
        self._container_count = 0
        self._team_count = 0

    # ------------------------------------------------------------- structure

    def add_container(
        self, parent_id: str | None, category: str | None = None
    ) -> ContainerDraft:
        """Add a grouping under a parent (or at the top level) and return it.

        The tier defaults to the depth's suggestion; an explicit category
        (the tree pane's New dropdown) overrides it.
        """
        siblings, depth = self._insertion_point(parent_id)
        self._container_count += 1
        if category is None:
            category = default_category_for_depth(depth)
        node = ContainerDraft(
            id=self._new_id(_CONTAINER_PREFIX),
            category=category,
            name=f"{category} {sequence_token(self._container_count)}",
            lead=self._names.draw(),
        )
        siblings.append(node)
        return node

    def add_team(self, parent_id: str | None) -> TeamDraft:
        """Add a team under a container (or at the top level) and return it."""
        siblings, _ = self._insertion_point(parent_id)
        self._team_count += 1
        node = TeamDraft(
            id=self._new_id(_TEAM_PREFIX),
            name=f"Team {sequence_token(self._team_count)}",
            owner=self._names.draw(),
        )
        siblings.append(node)
        return node

    def remove(self, node_id: str) -> None:
        """Remove a node and its subtree, pruning dependencies it carried."""
        node, siblings = self._locate(node_id)
        siblings.remove(node)
        removed = {team.id for team in teams_beneath(node)}
        self.dependencies = tuple(
            dep
            for dep in self.dependencies
            if dep.upstream not in removed and dep.downstream not in removed
        )

    def removal_summary(self, node_id: str) -> RemovalSummary:
        """What removing this node takes with it, for the confirm dialog."""
        node, _ = self._locate(node_id)
        teams = teams_beneath(node)
        return RemovalSummary(
            name=node.name,
            is_container=isinstance(node, ContainerDraft),
            team_count=len(teams),
            people=sum(team.people for team in teams),
        )

    def move_up(self, node_id: str) -> bool:
        """Swap the node one place earlier among its siblings."""
        node, siblings = self._locate(node_id)
        index = siblings.index(node)
        if index == 0:
            return False
        siblings[index - 1], siblings[index] = node, siblings[index - 1]
        return True

    def move_down(self, node_id: str) -> bool:
        """Swap the node one place later among its siblings."""
        node, siblings = self._locate(node_id)
        index = siblings.index(node)
        if index == len(siblings) - 1:
            return False
        siblings[index], siblings[index + 1] = siblings[index + 1], node
        return True

    def can_place(self, node_id: str, parent_id: str | None) -> bool:
        """Whether moving or copying a node under a parent would be legal.

        Illegal placements: into the node's own subtree, into a team and a
        unit under a lower tier than its own (a Company under a Division).
        The top level accepts anything.
        """
        node, _ = self._locate(node_id)
        if parent_id is None:
            return True
        if parent_id in (n.id for n in subtree(node)):
            return False
        target = self.find(parent_id)
        if not isinstance(target, ContainerDraft):
            return False
        if isinstance(node, ContainerDraft):
            return can_nest(node.category, target.category)
        return True

    def move_to(
        self, node_id: str, parent_id: str | None, index: int | None = None
    ) -> bool:
        """Reparent (and optionally position) a node, refusing illegal moves."""
        if not self.can_place(node_id, parent_id):
            return False
        node, siblings = self._locate(node_id)
        destination = self._children_of(parent_id)
        position = self._insert_index(siblings, node, destination, index)
        siblings.remove(node)
        destination.insert(position, node)
        return True

    def copy_into(self, node_id: str, parent_id: str | None, index: int | None = None):
        """Copy a subtree under a parent with fresh ids; None when illegal."""
        if not self.can_place(node_id, parent_id):
            return None
        node, _ = self._locate(node_id)
        copy = self._copy_node(node)
        destination = self._children_of(parent_id)
        destination.insert(len(destination) if index is None else index, copy)
        return copy

    def duplicate(self, node_id: str):
        """Copy a node (and its subtree) beside itself with fresh ids."""
        node, siblings = self._locate(node_id)
        copy = self._copy_node(node)
        copy.name = f"{node.name}{_DUPLICATE_SUFFIX}"
        siblings.insert(siblings.index(node) + 1, copy)
        return copy

    def reroll_name(self, current: str) -> str:
        """A fresh lead or owner name from the shared pool."""
        return self._names.reroll(current)

    # --------------------------------------------------------------- queries

    def find(self, node_id: str):
        """The node with this id, or None."""
        for node in self._walk():
            if node.id == node_id:
                return node
        return None

    def rollup(self, node_id: str) -> tuple[int, int]:
        """(teams, people) within a node's subtree, itself included."""
        node, _ = self._locate(node_id)
        teams = teams_beneath(node)
        return len(teams), sum(team.people for team in teams)

    def totals(self) -> tuple[int, int]:
        """(teams, people) across the whole draft."""
        teams = [node for node in self._walk() if isinstance(node, TeamDraft)]
        return len(teams), sum(team.people for team in teams)

    def teams(self) -> tuple[tuple[str, str], ...]:
        """(id, name) for every team, in tree order."""
        return tuple(
            (node.id, node.name) for node in self._walk() if isinstance(node, TeamDraft)
        )

    def container_paths(self) -> tuple[tuple[str, str], ...]:
        """(id, 'Company 1 / Division 2') for every container, in tree order."""
        paths: list[tuple[str, str]] = []

        def visit(node, prefix: str) -> None:
            if not isinstance(node, ContainerDraft):
                return
            label = f"{prefix} / {node.name}" if prefix else node.name
            paths.append((node.id, label))
            for child in node.children:
                visit(child, label)

        for root in self.roots:
            visit(root, "")
        return tuple(paths)

    def move_targets(self, node_id: str) -> tuple[tuple[str, str], ...]:
        """The containers a node may legally move into."""
        return tuple(
            (ident, path)
            for ident, path in self.container_paths()
            if self.can_place(node_id, ident)
        )

    def warnings(self) -> tuple[DraftWarning, ...]:
        """Containers with no teams anywhere beneath them."""
        return tuple(
            DraftWarning(
                node_id=node.id,
                message=f"{node.name} has no teams anywhere beneath it",
            )
            for node in self._walk()
            if isinstance(node, ContainerDraft) and not teams_beneath(node)
        )

    def blocking_reason(self) -> str | None:
        """Why OK must stay disabled, or None when the draft is acceptable."""
        team_count, people = self.totals()
        if team_count == 0:
            return "Add at least one team; an organisation needs one to score."
        if people <= 0:
            return "At least one team needs people in it."
        return None

    # -------------------------------------------------------------- internal

    def _children_of(self, parent_id: str | None) -> list:
        """The sibling list a legal placement under parent_id inserts into."""
        if parent_id is None:
            return self.roots
        parent, _ = self._locate(parent_id)
        return parent.children

    @staticmethod
    def _insert_index(
        siblings: list, node, destination: list, index: int | None
    ) -> int:
        """Where to insert after removal, correcting for a same-list shift."""
        if index is None:
            return len(destination) - (1 if destination is siblings else 0)
        if destination is siblings and siblings.index(node) < index:
            return index - 1
        return index

    def _new_id(self, prefix: str) -> str:
        existing = {node.id for node in self._walk()}
        while True:
            self._seq += 1
            candidate = f"{prefix}_{self._seq}"
            if candidate not in existing:
                return candidate

    def _insertion_point(self, parent_id: str | None) -> tuple[list, int]:
        """The sibling list and nesting depth for a new child of parent_id."""
        if parent_id is None:
            return self.roots, 0
        parent, _ = self._locate(parent_id)
        if not isinstance(parent, ContainerDraft):
            raise KeyError(f"not a container: {parent_id}")
        return parent.children, self._depth_of(parent) + 1

    def _depth_of(self, target) -> int:
        def search(nodes: list, depth: int) -> int | None:
            for node in nodes:
                if node is target:
                    return depth
                if isinstance(node, ContainerDraft):
                    found = search(node.children, depth + 1)
                    if found is not None:
                        return found
            return None

        return search(self.roots, 0)

    def _locate(self, node_id: str) -> tuple[object, list]:
        """The node and the sibling list holding it; raises on unknown ids."""

        def search(siblings: list):
            for node in siblings:
                if node.id == node_id:
                    return node, siblings
                if isinstance(node, ContainerDraft):
                    found = search(node.children)
                    if found is not None:
                        return found
            return None

        found = search(self.roots)
        if found is None:
            raise KeyError(f"unknown node: {node_id}")
        return found

    def _walk(self):
        yield from iter_nodes(self.roots)

    def _copy_node(self, node):
        if isinstance(node, TeamDraft):
            self._team_count += 1
            return TeamDraft(
                id=self._new_id(_TEAM_PREFIX),
                name=node.name,
                people=node.people,
                ships_without_asking=node.ships_without_asking,
                skew_percent=node.skew_percent,
                owner=node.owner,
                size=node.size,
            )
        self._container_count += 1
        copy = ContainerDraft(
            id=self._new_id(_CONTAINER_PREFIX),
            category=node.category,
            name=node.name,
            lead=node.lead,
            unit_headcount=node.unit_headcount,
        )
        copy.children = [self._copy_node(child) for child in node.children]
        return copy
