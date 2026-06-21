"""Organisation size bands: the rough scale a generated org is built to.

A band is a labelled people range the player picks before a random org is
generated. The generator targets the middle of the chosen band and builds a
hierarchy deep enough to hold that many people in real teams, so the org's
rolled-up headcount lands inside the range. The bands are pure data: the picker
dialog lists them and the generator reads their bounds; neither hard-codes a
number of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from fulcrum.domain.errors import InvalidOrgStateError

_MIN_PEOPLE: int = 1
_HALF: int = 2


@dataclass(frozen=True, slots=True)
class OrgSizeBand:
    """A pickable people range a random org can be generated to fill."""

    key: str
    label: str
    descriptor: str
    min_people: int
    max_people: int

    def __post_init__(self) -> None:
        if not self.key:
            raise InvalidOrgStateError("size band key must be a non-empty string")
        if not self.label:
            raise InvalidOrgStateError("size band label must be a non-empty string")
        if not self.descriptor:
            raise InvalidOrgStateError("size band descriptor must be non-empty")
        if self.min_people < _MIN_PEOPLE:
            raise InvalidOrgStateError(
                f"size band min_people must be at least {_MIN_PEOPLE}"
            )
        if self.max_people < self.min_people:
            raise InvalidOrgStateError("size band max_people must not be below min")

    @property
    def midpoint(self) -> int:
        """The middle of the range: the people count the generator aims for."""
        return (self.min_people + self.max_people) // _HALF

    def contains(self, people: int) -> bool:
        """Whether a people count falls inside this band."""
        return self.min_people <= people <= self.max_people


ORG_SIZE_BANDS: tuple[OrgSizeBand, ...] = (
    OrgSizeBand("tiny", "5 to 10 people", "A single team", 5, 10),
    OrgSizeBand("small", "25 to 150 people", "A small company", 25, 150),
    OrgSizeBand("medium", "150 to 1,500 people", "A division", 150, 1500),
    OrgSizeBand("large", "1,500 to 10,000 people", "A large company", 1500, 10000),
    OrgSizeBand("huge", "10,000 to 50,000 people", "An enterprise", 10000, 50000),
    OrgSizeBand(
        "massive",
        "50,000 to 250,000 people",
        "A global enterprise",
        50000,
        250000,
    ),
)

# The mid band is offered first: a recognisable org big enough to drill through
# without being so large that a first generation feels heavy.
DEFAULT_BAND: OrgSizeBand = ORG_SIZE_BANDS[2]
