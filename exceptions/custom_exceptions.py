# exceptions/custom_exceptions.py


class KarmaTrackError(Exception):
    """Base class for all custom exceptions in the KarmaTrack application."""

    pass


class PostProcessingError(KarmaTrackError):
    """Exception raised for errors during data processing (e.g., ranking, averaging)."""

    pass


class PostUnavailable(KarmaTrackError):
    """Exception raised when a post is unavailable (e.g., deleted, private)."""

    pass


class RankProcessingError(KarmaTrackError):
    """Exception raised for errors during rank processing operations."""

    pass


class BackupError(KarmaTrackError):
    """Exception raised for errors during data backup operations."""

    pass


class MalAPIError(KarmaTrackError):
    """Exception raised for errors related to external API interactions (MAL)."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(KarmaTrackError):
    """Exception raised for configuration-related errors (e.g., missing environment variables)."""

    pass


class DatabaseError(KarmaTrackError):
    """Exception raised for errors related to database operations (e.g., connection, query)."""

    pass
