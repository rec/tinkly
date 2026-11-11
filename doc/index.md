# Control Twinkly lights with Python

Tinkly lets Python programs find Twinkly controllers on the local network,
read their settings, change their output, and send RGB animation frames.
Each client connects to one controller. Python 3.12 or newer is required;
the installed library has no third-party runtime dependencies.

## Install

From a checkout of this repository, create an environment and install the library:

```sh
uv venv --python 3.12
uv pip install .
```

## Find a device and change its brightness

Connect your computer and lights to the same local network, then run:

```python
from tinkly.client import TwinklyClient
from tinkly.discovery import discover

devices = list(discover())
if not devices:
    raise SystemExit('No Twinkly devices found on the local network')

for device in devices:
    print(device.device_id, device.ip_address)

client = TwinklyClient(host=devices[0].ip_address)
print('Firmware:', client.firmware_version.data)
print('Brightness:', client.brightness.data)

client.brightness = {'mode': 'enabled', 'type': 'A', 'value': 75}
print('Updated brightness:', client.brightness.data)
```

This example chooses the first controller found. If you already know its address,
create the client directly with `TwinklyClient(host='192.168.1.23')`.

## Reading and writing settings

Reading a property sends a fresh request to the device. The result has two fields:
`data` contains the decoded JSON object, and `http_status` contains the HTTP status.
Writing a property sends the assigned dictionary to the device. Assignment does
not return a response; use `client.post()` if you need to inspect that response.

Firmware version and status can be read without authentication. Protected
requests obtain an authentication token automatically. Request failures raise
exceptions for your program to handle.

Authentication, echo, deleting a layout, starting a network scan, and switching
to realtime or off mode are methods because they perform actions.

## API reference

Choose the part of the library you need:

| Reference | What it covers |
| --- | --- |
| [HTTP client and settings](reference/tinkly/client.md) | Create a client, read and write properties, authenticate, and call endpoints directly. |
| [Device discovery](reference/tinkly/discovery.md) | Find controllers and read their addresses and identifiers. |
| [RGB frame transmission](reference/tinkly/frame.md) | Send packed RGB frames to a controller in realtime mode. |
| [Errors](reference/tinkly/errors.md) | Handle authentication, endpoint, discovery, and protocol failures. |
| [Authentication helpers](reference/tinkly/authentication.md) | Low-level MAC address and challenge-response functions. |

For multiple controllers, create one client per controller and send each its own
frame. Tinkly provides the transport; your application manages animation timing,
retries, reconnection, and coordination between controllers.

## Contributing

See [Building and checking the documentation](contributing.md) for the dev setup,
local build command, and generated-property documentation extension.
