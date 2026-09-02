"""Bit-packed binary reader for FC26's FIFA DB format."""

import struct
from typing import Optional
from .types import EFieldTypes


class DbReader:
    """Read bit-compressed integers, strings, and floats from a byte buffer."""

    def __init__(self, data: bytes):
        self._data = data
        self._byte_pos = 0
        self._current_byte = 0
        self._bit_pos = 8  # 8 means "need to load next byte"

    @property
    def position(self) -> int:
        """Current byte position in the buffer."""
        return self._byte_pos

    @position.setter
    def position(self, value: int):
        self._byte_pos = value
        self._bit_pos = 8  # Reset bit state when seeking

    def _ensure_byte(self):
        """Load the next byte if needed."""
        if self._bit_pos >= 8:
            self._current_byte = self._data[self._byte_pos]
            self._byte_pos += 1
            self._bit_pos = 0

    def read_bits(self, depth: int) -> int:
        """Read `depth` bits LSB-first. Returns unsigned integer.

        FC26 DB uses LSB-first bit order within each byte, and
        little-endian byte order within multi-byte fields.
        """
        if depth == 0:
            return 0
        value = 0
        remaining = depth
        bits_read = 0
        while remaining > 0:
            self._ensure_byte()
            bits_in_byte = min(8 - self._bit_pos, remaining)
            mask = (1 << bits_in_byte) - 1
            # LSB-first: extract bits starting from bit_pos without bit-reversal
            bits = (self._current_byte >> self._bit_pos) & mask
            # Little-endian accumulation: first chunk goes to LSB
            value = value | (bits << bits_read)
            self._bit_pos += bits_in_byte
            bits_read += bits_in_byte
            remaining -= bits_in_byte
        return value

    def read_integer(self, depth: int, range_low: int) -> int:
        """Read a bit-compressed integer field."""
        raw = self.read_bits(depth)
        return raw + range_low

    def read_float(self) -> float:
        """Read a 4-byte IEEE 754 float (little-endian)."""
        # Flush bit state — floats are byte-aligned
        self._bit_pos = 8
        val = struct.unpack_from("<f", self._data, self._byte_pos)[0]
        self._byte_pos += 4
        return val

    def read_string(self, length: int) -> str:
        """Read a null-terminated string of maximum byte length.

        FC26 stores text as UTF-8. The raw bytes are accumulated,
        then decoded as UTF-8 (falling back to Latin-1 for compatibility).
        """
        # Flush bit state — strings are byte-aligned
        self._bit_pos = 8
        raw = bytearray()
        start = self._byte_pos
        while self._byte_pos - start < length:
            b = self._data[self._byte_pos]
            self._byte_pos += 1
            if b == 0:
                # Skip remaining padding bytes
                remaining = length - (self._byte_pos - start)
                if remaining > 0:
                    self._byte_pos += remaining
                break
            raw.append(b)
        # Decode: try UTF-8 first, fall back to Latin-1
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def read_bytes(self, count: int) -> bytes:
        """Read raw bytes (byte-aligned)."""
        self._bit_pos = 8
        result = self._data[self._byte_pos : self._byte_pos + count]
        self._byte_pos += count
        return bytes(result)

    def skip_bits(self, count: int):
        """Skip `count` bits forward."""
        while count > 0:
            self._ensure_byte()
            skip = min(8 - self._bit_pos, count)
            self._bit_pos += skip
            count -= skip

    def seek_to_bit(self, absolute_bit: int):
        """Seek to an absolute bit position in the data buffer."""
        self._byte_pos = absolute_bit // 8
        remaining_bit = absolute_bit % 8
        if remaining_bit > 0:
            # Mid-byte: load the current byte and advance past it.
            # _ensure_byte will fire when remaining_bit bits are consumed
            # and will load the NEXT byte from byte_pos.
            self._bit_pos = remaining_bit
            self._current_byte = self._data[self._byte_pos]
            self._byte_pos += 1
        else:
            # Byte-aligned: signal _ensure_byte to load the byte on next read
            self._bit_pos = 8
            self._current_byte = 0

    def align_to_byte(self):
        """Skip remaining bits to reach next byte boundary."""
        if self._bit_pos > 0 and self._bit_pos < 8:
            self._bit_pos = 8

    @property
    def is_byte_aligned(self) -> bool:
        return self._bit_pos >= 8
