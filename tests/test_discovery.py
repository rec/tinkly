from __future__ import annotations

import unittest
from unittest.mock import patch

from tinkly.discovery import discover, parse_discovery_response
from tinkly.errors import DiscoveryError


class DiscoveryTests(unittest.TestCase):
    def test_parse_discovery_response(self) -> None:
        device = parse_discovery_response(b'\xab\x01\xa8\xc0OKTwinkly_A1234B\x00')

        self.assertEqual(device.ip_address, '192.168.1.171')
        self.assertEqual(device.device_id, 'Twinkly_A1234B')

    def test_rejects_bad_discovery_response(self) -> None:
        with self.assertRaises(DiscoveryError):
            parse_discovery_response(b'\xab\x01\xa8\xc0NOTwinkly_A1234B\x00')

    def test_discovery_stops_100ms_after_first_response(self) -> None:
        now = 0.0
        responses = iter(
            [
                (0.25, b'\x01\x01\xa8\xc0OKFirst\x00'),
                (0.30, b'\x02\x01\xa8\xc0OKSecond\x00'),
                (0.38, b'\x03\x01\xa8\xc0OKLate\x00'),
            ]
        )
        with patch('tinkly.discovery.socket.socket') as create_socket:
            sock = create_socket.return_value.__enter__.return_value

            def receive(size: int) -> tuple[bytes, tuple[str, int]]:
                nonlocal now
                arrival, data = next(responses)
                timeout = sock.settimeout.call_args.args[0]
                if arrival > now + timeout:
                    now += timeout
                    raise TimeoutError
                now = arrival
                return data, ('192.168.1.1', 5555)

            sock.recvfrom.side_effect = receive
            with patch('tinkly.discovery.time.monotonic', side_effect=lambda: now):
                devices = list(discover())

        self.assertEqual([d.device_id for d in devices], ['First', 'Second'])
        self.assertAlmostEqual(now, 0.35)
