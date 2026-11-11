"""Check generated documentation pages without running a web server."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


def check_pages(index: Path) -> int:
    """Reject broken internal page links and heading-only reachable pages.

    Follow local HTML links from index, including navigation links. External
    URLs and non-page assets are not fetched. Return the number of pages checked.
    """
    root = index.resolve().parent
    pending = [index.resolve()]
    seen: set[Path] = set()
    while pending:
        page = pending.pop()
        if page in seen:
            continue
        parsed = DocumentationPage()
        parsed.feed(page.read_text())
        if not parsed.content:
            raise ValueError(f'Blank documentation page: {page.relative_to(root)}')
        seen.add(page)
        for link in parsed.links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            path = unquote(url.path)
            target = (
                root / path.lstrip('/') if path.startswith('/') else page.parent / path
            ).resolve()
            if target.suffix not in ('', '.html'):
                continue
            if target.is_dir():
                target /= 'index.html'
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError(f'Broken documentation link in {page.name}: {link}')
            pending.append(target)
    return len(seen)


class DocumentationPage(HTMLParser):
    """Collect links and article text while excluding navigation and headings."""

    def __init__(self) -> None:
        """Initialize the page's links, article content, and parsing state."""
        super().__init__()
        self.links: list[str] = []
        self.content: list[str] = []
        self._article = False
        self._heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Collect anchor destinations and track article and heading boundaries."""
        if tag == 'a' and (href := dict(attrs).get('href')):
            self.links.append(href)
        if tag == 'article':
            self._article = True
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._heading = True

    def handle_endtag(self, tag: str) -> None:
        """Finish article and heading sections."""
        if tag == 'article':
            self._article = False
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._heading = False

    def handle_data(self, data: str) -> None:
        """Retain meaningful article text outside headings."""
        if self._article and not self._heading and data.strip():
            self.content.append(data.strip())
