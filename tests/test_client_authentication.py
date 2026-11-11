"""Exercise authentication and protocol failures through the HTTP boundary."""

import json
import unittest
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import MagicMock, patch

from tinkly.client import AuthToken, TwinklyClient
from tinkly.errors import AuthenticationError, ProtocolError


class AuthenticationTests(unittest.TestCase):
    def test_verified_token_is_cached_only_after_verification(self) -> None:
        device = TwinklyClient('device')
        login = connection(200, login_body('60'))
        verify = connection(200, b'{}')

        def verified_body() -> bytes:
            self.assertIsNone(device.token)
            return b'{}'

        verify.getresponse.return_value.read.side_effect = verified_body
        protected = connection(200, b'{"value":75}')
        with (
            patch(
                'tinkly.client.client.HTTPConnection',
                side_effect=[login, verify, protected],
            ),
            patch('tinkly.client.time.time', return_value=100.0),
        ):
            token = device.authenticate()
            self.assertIs(device.token, token)
            self.assertEqual(token.expires_at, 160.0)
            self.assertEqual(device.brightness.data, {'value': 75})
        self.assertEqual(
            verify.request.call_args.kwargs['headers']['X-Auth-Token'], 'secret-token'
        )
        self.assertEqual(
            protected.request.call_args.kwargs['headers']['X-Auth-Token'],
            'secret-token',
        )

    def test_failed_verification_is_not_reused_by_next_protected_request(self) -> None:
        offline = connection(200, b'{}')
        offline.request.side_effect = OSError('offline')
        for failure in (
            connection(500, b'failure'),
            connection(200, b'bad json'),
            connection(401, b''),
            offline,
        ):
            with self.subTest(failure=failure):
                device = TwinklyClient('device')
                retry_login = connection(200, login_body())
                with patch(
                    'tinkly.client.client.HTTPConnection',
                    side_effect=[
                        connection(200, login_body()),
                        failure,
                        retry_login,
                        connection(200, b'{}'),
                        connection(200, b'{}'),
                    ],
                ):
                    with self.assertRaises((ProtocolError, AuthenticationError)):
                        device.authenticate()
                    self.assertIsNone(device.token)
                    _ = device.brightness
                self.assertEqual(
                    retry_login.request.call_args.args[1], '/xled/v1/login'
                )

    def test_invalid_expiry_is_reported_without_verifying_or_caching(self) -> None:
        for expiry in (0, -1, '0', '-1', 'not-a-number', True, False, 1.5):
            with self.subTest(expiry=expiry):
                device = TwinklyClient('device')
                with patch(
                    'tinkly.client.client.HTTPConnection',
                    return_value=connection(200, login_body(expiry)),
                ) as create:
                    with self.assertRaisesRegex(
                        AuthenticationError, 'authentication_token_expires_in'
                    ):
                        device.authenticate()
                self.assertIsNone(device.token)
                self.assertEqual(create.call_count, 1)

    def test_expiry_during_verification_does_not_restart_login(self) -> None:
        device = TwinklyClient('device')
        verify = connection(200, b'{}')
        with (
            patch(
                'tinkly.client.client.HTTPConnection',
                side_effect=[connection(200, login_body(1)), verify],
            ) as create,
            patch('tinkly.client.time.time', side_effect=[100.0, 102.0]),
        ):
            with self.assertRaisesRegex(
                AuthenticationError, 'elapsed during verification'
            ):
                device.authenticate()
        self.assertIsNone(device.token)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(
            verify.request.call_args.kwargs['headers']['X-Auth-Token'], 'secret-token'
        )

    def test_http_failures_are_protocol_errors_and_close_connections(self) -> None:
        for phase, failure in (
            ('request', OSError('offline')),
            ('getresponse', BadStatusLine('invalid')),
            ('read', IncompleteRead(b'partial', 10)),
        ):
            with self.subTest(phase=phase):
                http = connection(200, b'{}')
                target = http.getresponse.return_value if phase == 'read' else http
                getattr(target, phase).side_effect = failure
                with patch('tinkly.client.client.HTTPConnection', return_value=http):
                    with self.assertRaises(ProtocolError) as raised:
                        TwinklyClient('device').get('status', authenticated=False)
                self.assertIs(raised.exception.__cause__, failure)
                http.close.assert_called_once()

    def test_credentials_are_absent_from_routine_representations_and_errors(
        self,
    ) -> None:
        token = AuthToken('secret-token', 'secret-response', None)
        device = TwinklyClient('device')
        device.token = token
        for representation in (repr(token), repr(device)):
            self.assertNotIn('secret-token', representation)
            self.assertNotIn('secret-response', representation)
        for status, raw in (
            (200, b'{"authentication_token":"secret-token",'),
            (200, b'["secret-token"]'),
            (200, b'{"code":"secret-token"}'),
            (404, b'secret-token'),
            (500, b'secret-token'),
        ):
            with self.subTest(status=status, raw=raw):
                with patch(
                    'tinkly.client.client.HTTPConnection',
                    return_value=connection(status, raw),
                ):
                    with self.assertRaises(ProtocolError) as raised:
                        device.authenticate()
                self.assertNotIn('secret-token', str(raised.exception))
                self.assertNotIn('secret-token', repr(raised.exception))


def connection(status: int, raw: bytes) -> MagicMock:
    """Create an HTTP connection returning one controlled response."""
    http = MagicMock()
    http.getresponse.return_value.status = status
    http.getresponse.return_value.read.return_value = raw
    return http


def login_body(expiry: object = None) -> bytes:
    """Encode a login response with the supplied expiry."""
    return json.dumps(
        {
            'authentication_token': 'secret-token',
            'challenge-response': 'secret-response',
            'authentication_token_expires_in': expiry,
        }
    ).encode()
