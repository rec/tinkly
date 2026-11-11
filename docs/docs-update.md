# Documentation build ownership and the Griffe extension

## Current setup

Tinkly uses reccy's shared documentation builder. Reccy configures Zensical,
generates the API reference with mkdocstrings and Griffe, runs a strict build,
and writes the site to `.cache/reccy-docs/site/`. It also owns GitHub Pages
publication.

Tinkly currently adds three Python helpers:

| File | Current responsibility | Intended owner |
| --- | --- | --- |
| [`scripts/build_docs.py`](../scripts/build_docs.py) | Build locally through reccy, run page checks, and print the result path. | A small local entry point may remain in tinkly; the shared build and checking behavior belong in reccy. |
| [`scripts/check_docs.py`](../scripts/check_docs.py) | Follow local HTML page links and reject missing pages or pages without article content beyond headings. | Reccy. This is generic documentation validation. |
| [`scripts/griffe_tinkly.py`](../scripts/griffe_tinkly.py) | Explain tinkly's generated endpoint properties and supply a package API overview. | Tinkly. This understands tinkly's API declarations. |

The tools are in the `dev` dependency group: `griffelib`, `reccy`, and `tyro`.
Development and documentation builds support Python 3.12. Tinkly's installed
runtime remains standard-library-only.

Published documentation source is Markdown in `doc/`; Python helpers live in
`scripts/`. This requested note lives in `docs/docs-update.md`, outside the
builder's configured `doc/` source directory.

## How the page checker ended up here

The first generated package index was effectively empty because
`tinkly/__init__.py` is empty. Local navigation also used directory URLs, which
open folder listings when followed through `file://` instead of automatically
opening `index.html`.

The documentation work addressed those symptoms by adding an API overview,
setting explicit HTML URLs, and introducing a checker in tinkly's local build
script. That checker was placed in the wrong project: it knows about HTML,
article content, and internal links, but nothing about Twinkly controllers or
tinkly's API.

There is also a behavior gap. Running `scripts/build_docs.py` performs the page
checks, but calling reccy's `Documentation.build()` directly bypasses them.
The shared builder and its publication path therefore do not provide the same
validation as tinkly's local wrapper.

## Why the Griffe extension is useful

The client declares endpoints compactly:

```python
firmware_version = getter('fw/version', authenticated=False)
brightness = setter('led/out/brightness')
```

`getter()` creates a read-only property. `setter()` creates a readable, writable
property using the same endpoint for GET and POST. Ordinary static analysis sees
factory assignments and does not infer their complete property behavior.

Reccy's configuration deliberately disables runtime inspection. The extension
teaches Griffe how to interpret these declarations without importing tinkly or
contacting lights. For each endpoint it:

- Labels the member as a property and, where appropriate, writable.
- Gives the read result the `TwinklyResponse` type in the generated reference.
- Documents the endpoint path and authentication requirement.
- Explains that reads make fresh GET requests.
- Explains that writes accept a JSON dictionary, POST it, propagate errors, and
  discard the response.
- Preserves the endpoint-specific docstring following the declaration.

These labels also keep the generated properties out of the documented dataclass
constructor parameters. The extension supplies a linked overview for the package
API index, avoiding an empty index without adding exports or other content to
`__init__.py`.

The value is a compact runtime API with useful generated documentation. The
endpoint path and access mode come from the declaration itself, reducing manual
duplication and documentation drift. The extension changes documentation metadata,
not runtime behavior or the runtime type checker's understanding of the properties.

## Existing integration points

[`pyproject.toml`](../pyproject.toml) configures reccy with:

```toml
[tool.reccy.documentation]
extensions = ["scripts/griffe_tinkly.py"]
use_directory_urls = false
```

Reccy already supports project-specific extension registration and URL style.
Those mechanisms belong in the shared builder. Tinkly's exact class name,
`getter`/`setter` interpretation, endpoint descriptions, and package overview
remain project-specific.

The current local build command is:

```sh
uv sync --python 3.12
uv run python scripts/build_docs.py
```

A future replacement must retain a build-only workflow. `reccy docs` currently
publishes documentation, so it is not an equivalent local preview command.

## Proposed follow-up

Move the generic checker and its behavioral tests from tinkly into reccy. Run
the checker as part of the shared build before returning success, so local builds
and publication receive the same validation. Then remove tinkly's duplicate
checker and simplify its local entry point around the shared behavior.

Keep the Griffe extension, its property-analysis tests, the guides, and extension
registration in tinkly. Reccy should provide extension loading without embedding
knowledge of Twinkly endpoints.

The checker also has known limitations recorded in
[`plan/issues.md`](../plan/issues.md), findings 8 and 9: its treatment of directory
and root-relative links does not match local-file browsing, and script/style
text can make an otherwise blank article pass. It does not verify fragment
targets, external URLs, or CSS/JavaScript visibility. These boundaries should
remain explicit during the transfer; passing the checker is not full browser QA.

The checker is still in tinkly. This note records the current implementation,
the ownership correction, and the proposed transfer; the transfer has not been
implemented.
