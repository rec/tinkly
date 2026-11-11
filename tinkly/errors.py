"""Exceptions for Twinkly protocol operations."""


class TinklyError(Exception):
    """Base error for Twinkly operations."""


class DiscoveryError(TinklyError):
    """A discovery reply has an invalid packet structure or status."""


class ProtocolError(TinklyError):
    """The device returned a response that does not match the protocol."""


class UnsupportedEndpointError(ProtocolError):
    """The device does not support a Twinkly endpoint."""

    def __init__(self, path: str, text: str) -> None:
        """Retain the API-relative endpoint and decoded HTTP 404 response body."""
        self.path = path
        self.text = text
        super().__init__(f'Twinkly endpoint {path!r} is not supported: {text}')


class AuthenticationError(TinklyError):
    """The authentication handshake failed."""
