"""Typed domain exception hierarchy for Fulcrum."""

from __future__ import annotations


class FulcrumError(Exception):
    """Base class for all Fulcrum domain errors."""


class InvalidOrgStateError(FulcrumError):
    """Raised when an organisational state violates a structural invariant."""


class InvalidMoveError(FulcrumError):
    """Raised when a move cannot be applied to a given state."""


class UnknownTeamError(FulcrumError):
    """Raised when a move or dependency references a team that does not exist."""
