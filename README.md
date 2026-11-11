# tinkly

Low-level Python communication with Twinkly lights, using only the standard
library. The package does not depend on lyte or NumPy.
Python 3.12 or newer is required.

This directory is a standalone Python project. Install it from its project directory:

```sh
uv pip install .
```

Lyte uses this project as a local editable dependency at `../tinkly` through
its own `pyproject.toml`.

## Device communication

The package provides UDP discovery, authentication, HTTP endpoint access, and
generation 2 realtime UDP v3 frame transmission. Existing device-facing types
retain the `Twinkly` spelling.

```python
from tinkly.client import TwinklyClient
from tinkly.discovery import discover
from tinkly.frame import send_frame

devices = list(discover(timeout=2.0))
client = TwinklyClient(host=devices[0].ip_address)
info = client.get('gestalt', authenticated=False).data
client.mac = str(info['mac'])
token = client.authenticate()

client.set_realtime_mode()
frame = bytes((255, 0, 0)) * int(str(info['number_of_led']))
send_frame(client.host, token.value, frame)
client.set_off_mode()
```

This illustrates one frame transmission. The caller controls repeated frame
delivery, pacing, token renewal, retries, reconnection, and shutdown. For repeated
transmissions, `send_frame` accepts a caller-owned UDP socket as `output`.
UDP sending uses `socket.sendto` on macOS, Linux, and Windows.

`TwinklyClient` exposes typed response records containing the HTTP status and
decoded JSON object. It provides named endpoint methods as well as `get`, `post`,
`post_bytes`, `delete`, and `request` for direct endpoint access. Protocol
exceptions are defined in `tinkly.errors`, under `TinklyError`.

## Frame buffers

Frames accept Python's buffer protocol through `collections.abc.Buffer`. Supply
C-contiguous unsigned bytes in RGB order, with three bytes per LED. Supported
inputs include `bytes`, `bytearray`, `array.array('B')`, `memoryview`, and
C-contiguous NumPy `uint8` arrays. Packet construction uses memoryviews without
copying pixel data. Sending combines each packet's header and payload into one
byte buffer for `sendto`. Keep mutable buffers unchanged until sending completes.

The transport treats the input as packed bytes; array shape validation belongs
to the caller. Array API compliance alone does not guarantee buffer support.
Arrays without a compatible host buffer must be converted by the caller.

## Tests

The tests use only the standard library. After installing the package,
run them from this directory:

```sh
python -m unittest discover -s tests
```

They use fake HTTP connections and sockets and do not contact lights. Playback,
animation, CLI commands, diagnostics, and retry policy remain in lyte.
