# Building and checking the documentation

The documentation tools are development dependencies. They require Python 3.12
or newer and are not installed with the runtime library.

From the repository root:

```sh
uv sync --python 3.12
uv run python scripts/build_docs.py
```

Open `.cache/reccy-docs/site/index.html` directly in your browser. The build uses
explicit HTML links so navigation works from disk. It also checks every page
reachable from the landing page for broken internal page links and empty content.
Generated HTML stays in the ignored `.cache/reccy-docs/` directory.

Reccy supplies the shared site builder. Griffe analyzes the package source
without importing tinkly or contacting devices. The extension in
`scripts/griffe_tinkly.py` describes the generated endpoint properties and gives
the package API index a module overview. Endpoint-specific descriptions come
from the docstrings following their declarations in `tinkly/client.py`.

Documentation source belongs in `doc/` as Markdown. Python build and verification
helpers belong in `scripts/`.

[Return to the usage guide](index.md).
