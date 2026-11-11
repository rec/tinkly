from __future__ import annotations

import unittest
from unittest.mock import patch

from tinkly.client import TWINKLY_API_PREFIX, AuthToken, TwinklyClient, TwinklyResponse
from tinkly.errors import ProtocolError, UnsupportedEndpointError


class FakeHttpResponse:
    def __init__(self, status: int, raw: bytes) -> None:
        self.status = status
        self.raw = raw

    def read(self) -> bytes:
        return self.raw


class FakeHttpConnection:
    response = FakeHttpResponse(200, b'{}')
    requests: list[
        tuple[str, int, float, str, str, bytes | None, dict[str, str] | None]
    ] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.requests.append(
            (self.host, self.port, self.timeout, method, url, body, headers)
        )

    def getresponse(self) -> FakeHttpResponse:
        return self.response

    def close(self) -> None:
        return None


class ClientTests(unittest.TestCase):
    def test_constructs_with_keyword_arguments(self) -> None:
        client = TwinklyClient(host='192.168.1.23', timeout=1.5)

        self.assertEqual(client.host, '192.168.1.23')
        self.assertEqual(client.timeout, 1.5)

    def test_delete_sends_authenticated_delete_request(self) -> None:
        FakeHttpConnection.response = FakeHttpResponse(200, b'{"code":1000}')
        FakeHttpConnection.requests = []
        client = TwinklyClient(host='192.168.1.23')
        client.token = AuthToken(
            value='test-token', challenge_response='', expires_at=None
        )

        with patch('tinkly.client.client.HTTPConnection', FakeHttpConnection):
            response = client.delete('movies')

        self.assertEqual(response.data, {'code': 1000})
        self.assertEqual(
            FakeHttpConnection.requests,
            [
                (
                    '192.168.1.23',
                    80,
                    5.0,
                    'DELETE',
                    f'{TWINKLY_API_PREFIX}/movies',
                    None,
                    {
                        'Content-Type': 'application/json',
                        'X-Auth-Token': 'test-token',
                    },
                )
            ],
        )

    def test_post_bytes_sends_binary_payload(self) -> None:
        FakeHttpConnection.response = FakeHttpResponse(200, b'{"code":1000}')
        FakeHttpConnection.requests = []

        with patch('tinkly.client.client.HTTPConnection', FakeHttpConnection):
            response = TwinklyClient(host='192.168.1.23').post_bytes(
                'movies/full',
                b'\x01\x02\x03',
                'application/octet-stream',
                authenticated=False,
            )

        self.assertEqual(response.data, {'code': 1000})
        self.assertEqual(
            FakeHttpConnection.requests,
            [
                (
                    '192.168.1.23',
                    80,
                    5.0,
                    'POST',
                    f'{TWINKLY_API_PREFIX}/movies/full',
                    b'\x01\x02\x03',
                    {
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': '3',
                    },
                )
            ],
        )

    def test_request_rejects_json_body_and_binary_payload(self) -> None:
        client = TwinklyClient(host='192.168.1.23')

        with self.assertRaisesRegex(ValueError, 'both JSON body and binary payload'):
            client.request(
                'POST',
                'movies/full',
                body={'code': 1000},
                payload=b'\x00',
                authenticated=False,
            )

    def test_404_raises_unsupported_endpoint_error(self) -> None:
        FakeHttpConnection.response = FakeHttpResponse(404, b'{"code":1101}')
        FakeHttpConnection.requests = []

        with (
            patch('tinkly.client.client.HTTPConnection', FakeHttpConnection),
            self.assertRaises(UnsupportedEndpointError) as raised,
        ):
            TwinklyClient(host='192.168.1.23').get('missing', authenticated=False)

        self.assertEqual(raised.exception.path, 'missing')
        self.assertEqual(raised.exception.text, '{"code":1101}')

    def test_firmware_version_and_status_use_unauthenticated_gets(self) -> None:
        calls = []

        def get(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append((self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with patch.object(TwinklyClient, 'get', get):
            _ = client.firmware_version
            _ = client.status

        self.assertEqual(
            calls,
            [
                ('192.168.1.23', 'fw/version', False),
                ('192.168.1.23', 'status', False),
            ],
        )

    def test_property_reads_fetch_fresh_responses(self) -> None:
        client = TwinklyClient(host='192.168.1.23')
        first = TwinklyResponse(http_status=200, data={'value': 50})
        second = TwinklyResponse(http_status=200, data={'value': 75})

        with patch.object(TwinklyClient, 'get', side_effect=[first, second]):
            self.assertIs(client.brightness, first)
            self.assertIs(client.brightness, second)

    def test_property_write_propagates_protocol_errors(self) -> None:
        client = TwinklyClient(host='192.168.1.23')

        with patch.object(TwinklyClient, 'post', side_effect=ProtocolError('rejected')):
            with self.assertRaisesRegex(ProtocolError, 'rejected'):
                client.brightness = {'value': 75}

    def test_device_name_summary_and_echo_use_documented_paths(self) -> None:
        calls = []

        def get(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('GET', self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        def post(
            self: TwinklyClient,
            path: str,
            body: dict[str, object],
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('POST', self.host, path, body, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with (
            patch.object(TwinklyClient, 'get', get),
            patch.object(TwinklyClient, 'post', post),
        ):
            _ = client.device_name
            _ = client.summary
            client.echo({'message': 'hello'})

        self.assertEqual(
            calls,
            [
                ('GET', '192.168.1.23', 'device_name', True),
                ('GET', '192.168.1.23', 'summary', True),
                ('POST', '192.168.1.23', 'echo', {'message': 'hello'}, True),
            ],
        )

    def test_brightness_and_saturation_use_documented_paths(self) -> None:
        calls = []

        def get(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('GET', self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000, 'value': 100})

        def post(
            self: TwinklyClient,
            path: str,
            body: dict[str, object],
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('POST', self.host, path, body, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with (
            patch.object(TwinklyClient, 'get', get),
            patch.object(TwinklyClient, 'post', post),
        ):
            _ = client.brightness
            client.brightness = {'mode': 'enabled', 'type': 'A', 'value': 75}
            _ = client.saturation
            client.saturation = {'mode': 'enabled', 'type': 'A', 'value': 80}

        self.assertEqual(
            calls,
            [
                ('GET', '192.168.1.23', 'led/out/brightness', True),
                (
                    'POST',
                    '192.168.1.23',
                    'led/out/brightness',
                    {'mode': 'enabled', 'type': 'A', 'value': 75},
                    True,
                ),
                ('GET', '192.168.1.23', 'led/out/saturation', True),
                (
                    'POST',
                    '192.168.1.23',
                    'led/out/saturation',
                    {'mode': 'enabled', 'type': 'A', 'value': 80},
                    True,
                ),
            ],
        )

    def test_mode_color_and_effects_use_documented_paths(self) -> None:
        calls = []

        def get(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('GET', self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        def post(
            self: TwinklyClient,
            path: str,
            body: dict[str, object],
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('POST', self.host, path, body, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with (
            patch.object(TwinklyClient, 'get', get),
            patch.object(TwinklyClient, 'post', post),
        ):
            _ = client.led_mode
            client.led_mode = {'mode': 'demo'}
            _ = client.led_color
            client.led_color = {'mode': 'rgb', 'red': 1, 'green': 2, 'blue': 3}
            _ = client.effects
            _ = client.current_effect
            client.current_effect = {'effect_id': 4}

        self.assertEqual(
            calls,
            [
                ('GET', '192.168.1.23', 'led/mode', True),
                ('POST', '192.168.1.23', 'led/mode', {'mode': 'demo'}, True),
                ('GET', '192.168.1.23', 'led/color', True),
                (
                    'POST',
                    '192.168.1.23',
                    'led/color',
                    {'mode': 'rgb', 'red': 1, 'green': 2, 'blue': 3},
                    True,
                ),
                ('GET', '192.168.1.23', 'led/effects', True),
                ('GET', '192.168.1.23', 'led/effects/current', True),
                (
                    'POST',
                    '192.168.1.23',
                    'led/effects/current',
                    {'effect_id': 4},
                    True,
                ),
            ],
        )

    def test_layout_and_led_config_use_documented_paths(self) -> None:
        calls = []

        def get(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('GET', self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        def post(
            self: TwinklyClient,
            path: str,
            body: dict[str, object],
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('POST', self.host, path, body, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        def delete(
            self: TwinklyClient,
            path: str,
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append(('DELETE', self.host, path, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with (
            patch.object(TwinklyClient, 'get', get),
            patch.object(TwinklyClient, 'post', post),
            patch.object(TwinklyClient, 'delete', delete),
        ):
            _ = client.layout_full
            client.layout_full = {'source': '3d'}
            client.delete_layout_full()
            _ = client.led_config
            client.led_config = {'strings': []}
            _ = client.timer
            client.timer = {'time_now': 1800, 'time_on': 3600, 'time_off': 7200}
            _ = client.movie_config
            _ = client.movies
            _ = client.current_movie
            _ = client.playlist
            _ = client.current_playlist_entry
            client.get_network_scan()
            _ = client.network_scan_results
            _ = client.network_status
            _ = client.mqtt_config
            _ = client.mic_config
            _ = client.mic_sample
            _ = client.music_drivers
            _ = client.music_driver_sets
            _ = client.current_music_driver_set

        self.assertEqual(
            calls,
            [
                ('GET', '192.168.1.23', 'led/layout/full', True),
                ('POST', '192.168.1.23', 'led/layout/full', {'source': '3d'}, True),
                ('DELETE', '192.168.1.23', 'led/layout/full', True),
                ('GET', '192.168.1.23', 'led/config', True),
                ('POST', '192.168.1.23', 'led/config', {'strings': []}, True),
                ('GET', '192.168.1.23', 'timer', True),
                (
                    'POST',
                    '192.168.1.23',
                    'timer',
                    {'time_now': 1800, 'time_on': 3600, 'time_off': 7200},
                    True,
                ),
                ('GET', '192.168.1.23', 'led/movie/config', True),
                ('GET', '192.168.1.23', 'movies', True),
                ('GET', '192.168.1.23', 'led/movies/current', True),
                ('GET', '192.168.1.23', 'playlist', True),
                ('GET', '192.168.1.23', 'playlist/current', True),
                ('GET', '192.168.1.23', 'network/scan', True),
                ('GET', '192.168.1.23', 'network/scan_results', True),
                ('GET', '192.168.1.23', 'network/status', True),
                ('GET', '192.168.1.23', 'mqtt/config', True),
                ('GET', '192.168.1.23', 'mic/config', True),
                ('GET', '192.168.1.23', 'mic/sample', True),
                ('GET', '192.168.1.23', 'music/drivers', True),
                ('GET', '192.168.1.23', 'music/drivers/sets', True),
                ('GET', '192.168.1.23', 'music/drivers/sets/current', True),
            ],
        )

    def test_set_off_mode_uses_led_mode_off(self) -> None:
        calls = []

        def post(
            self: TwinklyClient,
            path: str,
            body: dict[str, object],
            authenticated: bool = True,
        ) -> TwinklyResponse:
            calls.append((self.host, path, body, authenticated))
            return TwinklyResponse(http_status=200, data={'code': 1000})

        client = TwinklyClient(host='192.168.1.23')

        with patch.object(TwinklyClient, 'post', post):
            response = client.set_off_mode()

        self.assertEqual(response.data, {'code': 1000})
        self.assertEqual(
            calls,
            [('192.168.1.23', 'led/mode', {'mode': 'off'}, True)],
        )
