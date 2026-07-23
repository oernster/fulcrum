"""The editable draft of an organisation: the model behind the org editor.

The editor UI is a thin view over this draft. Every structural operation (add,
remove, move, duplicate) and every query (rollups, warnings, acceptance) lives
here, so the behaviour is tested under the coverage gate and the editor is a
pure function of the model. A draft converts losslessly to and from an
OrgBlueprint, which is also how an existing org re-enters the editor. The node
types themselves live in org_draft_nodes.
"""

from __future__ import annotations

from fulcrum.application.dto import DependencySpec, DomainSpec, OrgBlueprint, TeamSpec
from fulcrum.application.name_pool import NamePicker
from fulcrum.application.org_draft_nodes import (
    ContainerDraft,
    DraftWarning,
    RemovalSummary,
    TeamDraft,
    default_category_for_depth,
    iter_nodes,
    subtree,
    teams_beneath,
)

_PERCENT = 100

DEFAULT_WORKLOAD = 6

_TEAM_PREFIX = "team"
_CONTAINER_PREFIX = "domain"
_DUPLICATE_SUFFIX = " copy"


class OrgDraft:
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

    def add_container(self, parent_id: str | None) -> ContainerDraft:
        """Add a grouping under a parent (or at the top level) and return it."""
        siblings, depth = self._insertion_point(parent_id)
        self._container_count += 1
        category = default_category_for_depth(depth)
        node = ContainerDraft(
            id=self._new_id(_CONTAINER_PREFIX),
            category=category,
            name=f"{category} {self._container_count}",
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
            name=f"Team {self._team_count}",
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

    def move_to(self, node_id: str, parent_id: str | None) -> bool:
        """Reparent a node, refusing a move into its own subtree or itself."""
        node, siblings = self._locate(node_id)
        if parent_id is not None:
            if parent_id in (n.id for n in subtree(node)):
                return False
            target, _ = self._locate(parent_id)
            if not isinstance(target, ContainerDraft):
                return False
            destination = target.children
        else:
            destination = self.roots
        siblings.remove(node)
        destination.append(node)
        return True

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
        node, _ = self._locate(node_id)
        excluded = {n.id for n in subtree(node)}
        return tuple(
            (ident, path)
            for ident, path in self.container_paths()
            if ident not in excluded
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

    # --------------------------------------------------------- serialisation

    @classmethod
    def from_blueprint(cls, blueprint: OrgBlueprint, names: NamePicker) -> OrgDraft:
        """Rebuild an editable draft from a blueprint, filling blank names."""
        draft = cls(names, workload=blueprint.workload)
        containers: dict[str, ContainerDraft] = {}
        for spec in blueprint.domains:
            containers[spec.id] = ContainerDraft(
                id=spec.id,
                category=spec.category,
                name=spec.name,
                lead=spec.lead or names.draw(),
                unit_headcount=spec.headcount,
            )
        for spec in blueprint.domains:
            parent = containers.get(spec.parent_id) if spec.parent_id else None
            siblings = parent.children if parent is not None else draft.roots
            siblings.append(containers[spec.id])
        for team_spec in blueprint.teams:
            team = TeamDraft(
                id=team_spec.id,
                name=team_spec.name,
                people=team_spec.headcount,
                ships_without_asking=team_spec.has_local_authority,
                skew_percent=round(team_spec.incentive_skew * _PERCENT),
                owner=team_spec.owner or names.draw(),
                size=team_spec.size,
            )
            parent = (
                containers.get(team_spec.domain_id) if team_spec.domain_id else None
            )
            siblings = parent.children if parent is not None else draft.roots
            siblings.append(team)
        draft.dependencies = blueprint.dependencies
        draft._container_count = len(blueprint.domains)
        draft._team_count = len(blueprint.teams)
        return draft

    def to_blueprint(self) -> OrgBlueprint:
        """Serialise the draft back to the shared blueprint shape."""
        domains: list[DomainSpec] = []
        teams: list[TeamSpec] = []

        def visit(node, parent_id: str | None) -> None:
            if isinstance(node, ContainerDraft):
                domains.append(
                    DomainSpec(
                        id=node.id,
                        name=node.name or node.id,
                        parent_id=parent_id,
                        lead=node.lead,
                        category=node.category,
                        headcount=node.unit_headcount,
                    )
                )
                for child in node.children:
                    visit(child, node.id)
            else:
                teams.append(
                    TeamSpec(
                        id=node.id,
                        name=node.name or node.id,
                        has_local_authority=node.ships_without_asking,
                        incentive_skew=node.skew_percent / _PERCENT,
                        domain_id=parent_id,
                        size=node.size,
                        owner=node.owner,
                        headcount=node.people,
                    )
                )

        for root in self.roots:
            visit(root, None)
        team_ids = {team.id for team in teams}
        dependencies = tuple(
            dep
            for dep in self.dependencies
            if dep.upstream in team_ids and dep.downstream in team_ids
        )
        return OrgBlueprint(
            teams=tuple(teams),
            dependencies=dependencies,
            workload=self.workload,
            domains=tuple(domains),
        )

    # -------------------------------------------------------------- internal

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
