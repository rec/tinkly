import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_docs import check_pages


class DocumentationPageTests(unittest.TestCase):
    def test_checks_linked_pages_without_following_external_urls(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / 'index.html'
            index.write_text(
                '<article><h1>Home</h1><p>Usage guide.</p>'
                '<a href="client.html">Client</a>'
                '<a href="https://example.invalid/">External</a></article>'
            )
            (root / 'client.html').write_text(
                '<article><h1>Client</h1><p>Client API.</p>'
                '<a href="index.html">Home</a></article>'
            )

            self.assertEqual(check_pages(index), 2)

    def test_rejects_a_reachable_heading_only_page(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / 'index.html'
            index.write_text(
                '<article><p>Usage guide.</p><a href="empty.html">API</a></article>'
            )
            (root / 'empty.html').write_text(
                '<nav>Home Client Discovery</nav><article><h1>Index</h1></article>'
            )

            with self.assertRaisesRegex(ValueError, 'Blank documentation page: empty'):
                check_pages(index)

    def test_rejects_a_broken_page_link(self) -> None:
        with TemporaryDirectory() as directory:
            index = Path(directory) / 'index.html'
            index.write_text(
                '<article><p>Usage guide.</p><a href="missing.html">API</a></article>'
            )

            with self.assertRaisesRegex(ValueError, 'Broken documentation link'):
                check_pages(index)
