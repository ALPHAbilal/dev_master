"""Errors raised by the backend boundary, never by an SDK-specific layer."""


class TutorV2Error(Exception):
    """Base class for all v2 backend errors."""


class ValidationError(TutorV2Error):
    """A caller supplied data outside the allowed contract."""


class InvariantError(TutorV2Error):
    """A mutation would violate a one-home or lifecycle rule."""


class CapabilityUnavailableError(TutorV2Error):
    """A scoped capability is not available in the current wakeup."""


class StaleWorkspaceRevisionError(TutorV2Error):
    """A guarded workspace write was based on an old revision."""
