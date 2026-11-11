# Documentation build ownership and the Griffe extension

Tinkly uses reccy's shared documentation builder. Reccy configures Zensical,
generates the API reference with mkdocstrings and Griffe, runs a strict build,
checks the generated HTML, and writes the site to `.cache/reccy-docs/site/`.
It also owns GitHub Pages publication.

## Shared page validation

The generic page checker and its behavioral tests now live in reccy.
`Documentation.build()` checks reachable pages before returning, so both local
builds and publication receive the same validation. Tinkly's
[`scripts/build_docs.py`](../scripts/build_docs.py) is a small build-only entry
point; it no longer implements or invokes a separate checker.

The checker rejects broken internal page links and pages without article content
or links to child documentation. It excludes script and style text and resolves
links using the hosted site's URL prefix, including GitHub Pages repository paths.
Directory links are accepted only when directory URLs are configured. Heading-only
package indexes can link to child pages without artificial descriptions.

This addresses the checker defects recorded in findings 8 and 9 of
[`plan/issues.md`](../plan/issues.md). With directory URLs off, root-relative page
links are also rejected because they fail under `file://`. The checker does not
check fragment targets, external URLs, assets, or CSS/JavaScript visibility, and
does not replace browser inspection.

## Project-specific Griffe extension

[`scripts/griffe_tinkly.py`](../scripts/griffe_tinkly.py) remains in tinkly, along
with its property-analysis tests. It interprets declarations such as:

```python
firmware_version = getter('fw/version', authenticated=False)
brightness = setter('led/out/brightness')
```

Without importing tinkly or contacting lights, the extension describes each
property's endpoint, authentication requirement, response type, read/write
behavior, and endpoint-specific docstring. It also supplies the package API
overview. Those details belong with tinkly's declarations, rather than in reccy.

[`pyproject.toml`](../pyproject.toml) registers the extension and selects explicit
HTML URLs for local browsing:

```toml
[tool.reccy.documentation]
extensions = ["scripts/griffe_tinkly.py"]
use_directory_urls = false
```

Build locally without publishing:

```sh
uv sync --python 3.12
uv run python scripts/build_docs.py
```

`reccy docs` builds and publishes, so it is not a build-only replacement.
Documentation tools are development dependencies; tinkly's installed runtime
remains standard-library-only.
