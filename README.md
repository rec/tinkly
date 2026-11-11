# tinkly: a tiny interface to Twinkly v2 lights

I love the Twinkly lights but the [xled library](https://github.com/scrool/xled) is
filled with complicated cruft which obscures the actual communication layer, and seems
to no longer be in development.

In particular, xled has a totally unnecessary ZMQ queue that
slows everything down and prevents two clients from existing.

I re-implemented just the Twinkly communication part, and left all the other
parts behind. In particular, there is no CLI - for that, you'll have to see my
upcoming general project, "lyte".

## Device communication

This package provides UDP discovery, authentication, HTTP endpoint access for generation
2 Twinkly lights.

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

## Frame buffers

`lyte` uses `numpy`, but I decided not to make that a dependency. Instead, we use
Python's buffer protocol `collections.abc.Buffer`. The input is C-style unsigned bytes
in RGB order, with three bytes per LED.  Supported inputs include `bytes`, `bytearray`,
`array.array('B')`, `memoryview`, and C-contiguous NumPy `uint8` arrays.

## The API

https://rec.github.io/tinkly/
