# tinkly

Tinkly provides discovery, authentication, HTTP endpoint access, and realtime
UDP frame transmission for Twinkly lights. It requires Python 3.12 or newer
and uses only the standard library at runtime.

## Endpoint properties

Read an endpoint property to make an HTTP GET request. Each read returns a fresh
`TwinklyResponse` containing the HTTP status and decoded JSON data:

```python
response = client.firmware_version
brightness = client.brightness.data
```

Firmware version and status do not require authentication. Other properties
authenticate automatically when necessary.

Writable properties accept the device's JSON body:

```python
client.brightness = {'mode': 'enabled', 'type': 'A', 'value': 75}
```

Assignment makes an HTTP POST and propagates errors. It does not return a
response; use `client.post()` when the response is needed. The generated API
reference identifies readable and writable properties and their endpoint paths.

Authentication, echo, layout deletion, network scanning, and realtime/off mode
switching remain methods. Generic HTTP methods provide direct endpoint access.

## Discovery and frames

`discover()` waits up to two seconds for the first device, then collects responses
for another 100 ms. Its timeout and grouping window can be configured.

`send_frame()` sends a packed RGB frame through the generation 2 realtime UDP
protocol. The caller controls repeated transmission, pacing, authentication
renewal, retries, reconnection, and shutdown. Frames support contiguous unsigned
byte buffers, including NumPy arrays, without requiring NumPy as a dependency.

## Building this documentation

The documentation tools are development dependencies and require Python 3.13 or
newer. From the repository root:

```sh
uv sync --python 3.13
uv run python scripts/build_docs.py
```

Open `.cache/reccy-docs/site/index.html` to view the result. Griffe analyzes the
Python source without importing tinkly or contacting devices. The project-specific
extension in `scripts/griffe_tinkly.py` recognizes the endpoint property factories.
