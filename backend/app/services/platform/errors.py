"""Typed errors raised by platform connectors.

They subclass RuntimeError so older call sites that catch RuntimeError keep
working, but carry an HTTP status so the API layer can answer precisely
instead of turning every upstream hiccup into a generic 500.
"""


class ConnectorError(RuntimeError):
    """Base class for connector failures. ``status_code`` is what the API returns."""

    status_code = 502

    def __init__(self, message: str, *, platform: str = ""):
        super().__init__(message)
        self.platform = platform


class UpstreamUnavailableError(ConnectorError):
    """The platform could not be reached (timeout, DNS, 5xx)."""

    status_code = 502


class RateLimitedError(ConnectorError):
    """The platform asked us to slow down (HTTP 429)."""

    status_code = 429


class UpstreamFormatError(ConnectorError):
    """The platform answered, but not in a shape we understand (layout change)."""

    status_code = 502


class IncompleteHistoryError(UpstreamUnavailableError):
    """The platform pagination limit was reached without establishing that history is complete."""

    status_code = 502

