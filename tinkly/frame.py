"""Generation 2 realtime UDP frame sender using protocol version 3."""

from __future__ import annotations

import base64
import binascii
import socket
from collections.abc import Buffer, Iterable

from .errors import ProtocolError

REALTIME_PORT = 7777
# Twinkly UDP v3 limits each fragment's pixel payload to 900 bytes, excluding headers.
# https://xled-docs.readthedocs.io/en/latest/protocol_details.html#version-3
MAX_FRAGMENT_SIZE = 900


def frame_packets(
    token: str,
    frame: Buffer,
) -> Iterable[tuple[bytes, memoryview]]:
    """Yield protocol v3 headers and pixel payload views for one RGB frame.

    Args:
        token: Base64 authentication token decoding to exactly eight bytes.
        frame: Contiguous unsigned bytes containing three bytes per RGB LED.

    Each pair contains a twelve-byte header and up to 900 bytes of pixel data.
    Payload views share the input buffer, which must remain unchanged during
    transmission. Fragment numbers start at zero and fit in one byte.

    Validation happens as the iterator is consumed. Invalid tokens or more
    than 256 fragments raise ProtocolError; invalid RGB buffers raise ValueError.
    """
    try:
        raw_token = base64.b64decode(token, validate=True)
    except binascii.Error as err:
        raise ProtocolError('Twinkly realtime token is not valid base64') from err
    if len(raw_token) != 8:
        raise ProtocolError('Twinkly realtime token must decode to 8 bytes')
    payload = frame_payload(frame)
    for index, start in enumerate(range(0, len(payload), MAX_FRAGMENT_SIZE)):
        fragment = payload[start : start + MAX_FRAGMENT_SIZE]
        if index > 255:
            raise ProtocolError(
                'Realtime frame is too large for one-byte fragment numbers'
            )
        yield b'\x03' + raw_token + b'\x00\x00' + bytes((index,)), fragment


def send_frame(
    host: str, token: str, frame: Buffer, output: socket.socket | None = None
) -> int:
    """Send one RGB frame to UDP port 7777 and return total datagram bytes sent.

    Args:
        host: Device hostname or IPv4 address.
        token: Base64 token obtained through authentication.
        frame: Contiguous unsigned RGB bytes, three per LED.
        output: Optional caller-owned UDP socket. If omitted, create a socket
            for this call and close it afterward. A supplied socket stays open.

    Authenticate and switch the device to realtime mode before calling. This
    function sends the fragments once without pacing, retries, or token renewal.
    The byte count includes packet headers. Buffer validation, protocol, and
    socket errors propagate; earlier fragments may already have been sent.
    """
    if output is not None:
        return _send_frame(output, host, token, frame)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        return _send_frame(sock, host, token, frame)


def _send_frame(output: socket.socket, host: str, token: str, frame: Buffer) -> int:
    """Send each header and payload as one datagram through an existing socket."""
    sent = 0
    address = (host, REALTIME_PORT)
    for header, payload in frame_packets(token, frame):
        sent += output.sendto(b''.join((header, payload)), address)
    return sent


def frame_payload(frame: Buffer) -> memoryview:
    """Expose an RGB buffer as a flat unsigned-byte memoryview without copying.

    Accept buffers with format B and C-contiguous storage, including
    multidimensional views. The byte count must be divisible by three.
    Raise ValueError for a different element format, non-contiguous storage,
    or an incomplete RGB pixel. The returned view shares the input buffer.
    """
    view = memoryview(frame)
    if view.format != 'B':
        raise ValueError('Realtime frames must contain unsigned bytes')
    if not view.c_contiguous:
        raise ValueError('Realtime frames must be C-contiguous')
    payload = view.cast('B')
    if len(payload) % 3:
        raise ValueError('Realtime frames must contain three bytes per LED')
    return payload
