class EnforcementError(Exception):
    """Raised when deterministic enforcement encounters an unrecoverable error."""


class PublicationBlocked(Exception):
    """Raised when publication is explicitly blocked by enforcement rules."""