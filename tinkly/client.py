"""Small HTTP client for Twinkly devices."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from http import client

from .authentication import make_challenge_response
from .errors import AuthenticationError, ProtocolError, UnsupportedEndpointError

AUTH_HEADER = 'X-Auth-Token'
TWINKLY_API_PREFIX = '/' + 'x' + 'led/v1'


def getter(path: str, authenticated: bool = True) -> property:
    """Create a read-only endpoint property returning a fresh TwinklyResponse.

    Args:
        path: Endpoint relative to the device's `/xled/v1/` API prefix.
        authenticated: Obtain a token if needed and include it in each request.

    Reading the property performs an HTTP GET every time; results are not cached.
    Request errors propagate to the caller.
    """

    def read(self: TwinklyClient) -> TwinklyResponse:
        """Fetch the endpoint using this property's authentication setting."""
        return self.get(path, authenticated=authenticated)

    return property(read)


def setter(path: str) -> property:
    """Create a readable, writable authenticated endpoint property.

    Reads perform HTTP GET and return a fresh TwinklyResponse. Assignments
    accept a `dict[str, object]` JSON body and perform HTTP POST to the same
    path, relative to `/xled/v1/`. Assignment discards the response; use
    TwinklyClient.post when its result is needed. Request errors propagate.
    """

    def write(self: TwinklyClient, body: dict[str, object]) -> None:
        """POST the assigned JSON body and discard the response."""
        self.post(path, body)

    return getter(path).setter(write)


@dataclass(frozen=True)
class TwinklyResponse:
    """Successful HTTP response and its decoded JSON object."""

    http_status: int
    """HTTP status code returned by the device."""
    data: dict[str, object]
    """Decoded JSON body, including any device application status code."""


@dataclass(frozen=True)
class AuthToken:
    """Authentication token, verification response, and optional expiry time."""

    value: str
    """Base64 token used in HTTP headers and decoded for realtime UDP packets."""
    challenge_response: str
    """Challenge response returned by login and sent back during verification."""
    expires_at: float | None
    """Expiry as Unix time in seconds, or None if the device supplied no expiry."""

    @property
    def expired(self) -> bool:
        """Whether the known expiry time has passed; False if no expiry is known."""
        return self.expires_at is not None and self.expires_at <= time.time()


@dataclass
class TwinklyClient:
    """Synchronous HTTP client for a single Twinkly device.

    Endpoint properties return TwinklyResponse records on every read. Writable
    properties POST assigned JSON dictionaries. Authentication is automatic
    for protected endpoints. Each request opens and closes an HTTP connection;
    retries, realtime frame pacing, and reconnection belong to the caller.
    """

    host: str
    """Device hostname or IPv4 address; HTTP requests use port 80."""
    mac: str | None = None
    """Optional MAC address used to check the login challenge response."""
    timeout: float = 5.0
    """HTTP connection and socket operation timeout in seconds."""
    token: AuthToken | None = field(default=None, init=False)
    """Current authentication token, obtained automatically when needed."""

    # Getters
    current_movie = getter('led/movies/current')
    """Read the device's current movie selection."""
    current_music_driver_set = getter('music/drivers/sets/current')
    """Read the currently selected music driver set."""
    current_playlist_entry = getter('playlist/current')
    """Read the current entry in the device playlist."""
    device_name = getter('device_name')
    """Read the device's configured name."""
    effects = getter('led/effects')
    """Read the effects available on the device."""
    firmware_version = getter('fw/version', authenticated=False)
    """Read the firmware version without logging in."""
    mic_config = getter('mic/config')
    """Read the device's microphone configuration."""
    mic_sample = getter('mic/sample')
    """Read a microphone sample reported by the device."""
    movie_config = getter('led/movie/config')
    """Read the device's movie playback configuration."""
    movies = getter('movies')
    """Read the device's stored movie listing."""
    mqtt_config = getter('mqtt/config')
    """Read the device's MQTT configuration."""
    music_driver_sets = getter('music/drivers/sets')
    """Read the available music driver sets."""
    music_drivers = getter('music/drivers')
    """Read the music drivers available on the device."""
    network_scan_results = getter('network/scan_results')
    """Read Wi-Fi scan results after starting a scan with get_network_scan()."""
    network_status = getter('network/status')
    """Read the device's current network status."""
    playlist = getter('playlist')
    """Read the device's configured playlist."""
    status = getter('status', authenticated=False)
    """Read device status without logging in."""
    summary = getter('summary')
    """Read the device summary supplied by the summary endpoint."""

    # Setters
    brightness = setter('led/out/brightness')
    """Read or update output brightness using mode, type, and value fields."""
    current_effect = setter('led/effects/current')
    """Read the selected effect or select one by assigning an effect_id body."""
    layout_full = setter('led/layout/full')
    """Read or upload the full LED layout, including coordinates and source."""
    led_color = setter('led/color')
    """Read or update the static LED color using the device's color fields."""
    led_config = setter('led/config')
    """Read or update the device's LED string configuration."""
    led_mode = setter('led/mode')
    """Read the operating mode or set it by assigning a body with a mode field."""
    saturation = setter('led/out/saturation')
    """Read or update output saturation using mode, type, and value fields."""
    timer = setter('timer')
    """Read or update the device timer's time_now, time_on, and time_off fields."""

    def authenticate(self) -> AuthToken:
        """Log in with a random challenge, verify the issued token, and return it.

        Store the token on this client and calculate its expiry when supplied
        by the device. If mac is set, check the returned challenge response
        before verification. Authentication and request failures propagate.
        """
        challenge = os.urandom(32)
        login = self.post(
            'login',
            {'challenge': base64.b64encode(challenge).decode()},
            authenticated=False,
        )
        data = login.data
        token = _required_str(data, 'authentication_token')
        challenge_response = _required_str(data, 'challenge-response')

        if self.mac is not None:
            expected = make_challenge_response(challenge, self.mac)
            if challenge_response != expected:
                raise AuthenticationError(
                    'Device challenge-response did not match the expected value'
                )

        expires_in = data.get('authentication_token_expires_in')
        expires_at = None
        if expires_in is not None:
            if not isinstance(expires_in, int | str):
                raise AuthenticationError(
                    'Login response did not contain numeric '
                    "'authentication_token_expires_in'"
                )
            expires_at = time.time() + int(expires_in)

        self.token = AuthToken(
            value=token,
            challenge_response=challenge_response,
            expires_at=expires_at,
        )
        self.post(
            'verify',
            {'challenge_response': challenge_response},
            authenticated=True,
        )
        return self.token

    def get(self, path: str, authenticated: bool = True) -> TwinklyResponse:
        """GET an API-relative endpoint, optionally obtaining and sending a token."""
        return self.request('GET', path, authenticated=authenticated)

    def post(
        self,
        path: str,
        body: dict[str, object],
        authenticated: bool = True,
    ) -> TwinklyResponse:
        """POST a JSON object to an API-relative endpoint and return its response.

        Authentication is enabled by default; login uses authenticated=False.
        """
        return self.request('POST', path, body=body, authenticated=authenticated)

    def post_bytes(
        self,
        path: str,
        payload: bytes,
        content_type: str,
        authenticated: bool = True,
    ) -> TwinklyResponse:
        """POST raw bytes with the supplied Content-Type and return the response.

        The path is relative to `/xled/v1/`. Content-Length is calculated from
        payload. Authentication is enabled unless explicitly disabled.
        """
        return self.request(
            'POST',
            path,
            payload=payload,
            content_type=content_type,
            authenticated=authenticated,
        )

    def delete(self, path: str) -> TwinklyResponse:
        """DELETE an API-relative endpoint using authentication."""
        return self.request('DELETE', path)

    def echo(self, body: dict[str, object]) -> TwinklyResponse:
        """POST a JSON object to the authenticated echo endpoint."""
        return self.post('echo', body)

    def delete_layout_full(self) -> TwinklyResponse:
        """Delete the device's full LED layout and return its response."""
        return self.delete('led/layout/full')

    def get_network_scan(self) -> TwinklyResponse:
        """Start a Wi-Fi network scan and return the device's acknowledgement.

        Read network_scan_results separately once the scan has completed.
        This method does not wait or poll for completion.
        """
        return self.get('network/scan')

    def set_realtime_mode(self) -> TwinklyResponse:
        """Switch to realtime LED mode before sending UDP frames."""
        return self.post('led/mode', {'mode': 'rt'})

    def set_off_mode(self) -> TwinklyResponse:
        """Switch to off mode to turn off the device's LEDs."""
        return self.post('led/mode', {'mode': 'off'})

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        payload: bytes | None = None,
        content_type: str = 'application/json',
        authenticated: bool = True,
    ) -> TwinklyResponse:
        """Send one HTTP request and validate the JSON object response.

        Args:
            method: HTTP method such as GET, POST, or DELETE.
            path: Endpoint relative to `/xled/v1/`, without a leading slash.
            body: Optional JSON object; cannot be combined with payload.
            payload: Optional raw request bytes.
            content_type: Content-Type header; defaults to application/json.
            authenticated: Obtain a token if needed and send X-Auth-Token.

        Returns:
            HTTP status and decoded JSON data. An empty response body is
            treated as an empty JSON object.

        Raises:
            ValueError: Both body and payload were supplied.
            AuthenticationError: Authentication fails or HTTP 401 is returned.
                HTTP 401 also clears the stored token.
            UnsupportedEndpointError: The device returns HTTP 404.
            ProtocolError: Sending or reading raises OSError, another HTTP
                error is returned, the body is not a valid UTF-8 JSON object,
                or a supplied application code is not 1000.
        """
        if body is not None and payload is not None:
            raise ValueError('request cannot use both JSON body and binary payload')
        headers = {'Content-Type': content_type}
        if authenticated:
            headers[AUTH_HEADER] = self._auth_token()
        if body is not None:
            payload = json.dumps(body).encode()
        if payload is not None:
            headers['Content-Length'] = str(len(payload))

        connection = client.HTTPConnection(self.host, 80, timeout=self.timeout)
        try:
            connection.request(
                method,
                f'{TWINKLY_API_PREFIX}/{path}',
                body=payload,
                headers=headers,
            )
            response = connection.getresponse()
            raw = response.read()
        except OSError as err:
            raise ProtocolError(
                f'Could not reach Twinkly device at {self.host}: {err}'
            ) from err
        finally:
            connection.close()

        if response.status == 401:
            self.token = None
            raise AuthenticationError('Device rejected the authentication token')
        if response.status == 404:
            text = raw.decode(errors='replace')
            raise UnsupportedEndpointError(path, text)
        if response.status < 200 or response.status >= 300:
            text = raw.decode(errors='replace')
            raise ProtocolError(f'HTTP {response.status} from {self.host}: {text}')

        try:
            data = json.loads(raw.decode() or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise ProtocolError(f'Device returned invalid JSON: {raw!r}') from err
        if not isinstance(data, dict):
            raise ProtocolError(f'Device returned a non-object JSON response: {data!r}')

        code = data.get('code')
        if code is not None and code != 1000:
            raise ProtocolError(f'Twinkly application code {code}: {data!r}')
        return TwinklyResponse(http_status=response.status, data=data)

    def _auth_token(self) -> str:
        """Return the current token, authenticating if it is missing or expired."""
        if self.token is None or self.token.expired:
            self.authenticate()
        if self.token is None:
            raise AuthenticationError('Authentication did not produce a token')
        return self.token.value


def _required_str(data: dict[str, object], key: str) -> str:
    """Read a required login string or raise AuthenticationError."""
    value = data.get(key)
    if not isinstance(value, str):
        raise AuthenticationError(f'Login response did not contain string {key!r}')
    return value
