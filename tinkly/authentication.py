"""Cryptographic helpers used by Twinkly authentication."""

from __future__ import annotations

import hashlib
import itertools
import re

CHALLENGE_KEY = b'evenmoresecret!!'


def mac_bytes(mac: str) -> bytes:
    """Decode a MAC address into six bytes, ignoring non-hex separators.

    Raises:
        ValueError: The address does not contain exactly twelve hex digits.
    """
    compact = re.sub(r'[^0-9a-fA-F]', '', mac)
    if len(compact) != 12:
        raise ValueError(f'MAC address must contain 12 hex digits: {mac!r}')
    try:
        return bytes.fromhex(compact)
    except ValueError as err:
        raise ValueError(f'MAC address contains non-hex characters: {mac!r}') from err


def xor_repeating(message: bytes, key: bytes) -> bytes:
    """XOR each message byte with a cycling key and return the resulting bytes.

    An empty key produces an empty result.
    """
    return bytes(m ^ k for m, k in zip(message, itertools.cycle(key)))


def derive_key(shared_key: bytes, mac: str) -> bytes:
    """XOR a shared key with the repeating six-byte device MAC address."""
    return xor_repeating(shared_key, mac_bytes(mac))


def rc4(message: bytes, key: bytes) -> bytes:
    """Apply RC4 to a message using a non-empty key.

    The same operation encrypts and decrypts. This reproduces the cipher used
    by the device's authentication protocol.
    """
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]

    output = bytearray()
    i = 0
    j = 0
    for b in message:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        output.append(b ^ state[(state[i] + state[j]) % 256])
    return bytes(output)


def make_challenge_response(challenge: bytes, mac: str) -> str:
    """Return the device authentication response as a SHA-1 hex digest.

    Encrypt the raw challenge with RC4 using the shared key combined with the
    device MAC address, then hash the encrypted bytes.
    """
    encrypted = rc4(challenge, derive_key(CHALLENGE_KEY, mac))
    return hashlib.sha1(encrypted).hexdigest()
