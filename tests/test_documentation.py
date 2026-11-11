from __future__ import annotations

import unittest
from pathlib import Path

import griffe


class DocumentationTests(unittest.TestCase):
    def test_endpoint_properties_are_documented_without_importing_tinkly(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module = griffe.load(
            'tinkly.client',
            search_paths=[root],
            extensions=griffe.load_extensions(
                str(root / 'scripts' / 'griffe_tinkly.py')
            ),
            allow_inspection=False,
        )
        client = module['TwinklyClient']
        brightness = client['brightness']
        firmware = client['firmware_version']
        status = client['status']

        self.assertEqual(brightness.labels, {'property', 'writable'})
        self.assertEqual(str(brightness.annotation), 'TwinklyResponse')
        self.assertIsNone(brightness.value)
        self.assertIn('GET led/out/brightness', brightness.docstring.value)
        self.assertIn('POST led/out/brightness', brightness.docstring.value)
        self.assertIn('dict[str, object]', brightness.docstring.value)
        self.assertIn('Authentication is required', brightness.docstring.value)
        for attribute in (firmware, status):
            with self.subTest(property=attribute.name):
                self.assertEqual(attribute.labels, {'property'})
                self.assertIn(
                    'Authentication is not required', attribute.docstring.value
                )
                self.assertIn('read-only', attribute.docstring.value)
        self.assertIn('GET fw/version', firmware.docstring.value)
        self.assertIn('GET status', status.docstring.value)
        self.assertEqual(
            [p.name for p in client.parameters],
            ['self', 'host', 'mac', 'timeout'],
        )
        self.assertNotIn('property', client['host'].labels)
        self.assertIsInstance(client['authenticate'], griffe.Function)
