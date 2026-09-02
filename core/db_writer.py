"""DbWriter — bit-packed binary writer for FIFA DB format.

Inverse of DbReader. Writes integers as bit-packed LSB-first values
with little-endian byte order, matching the FIFA DB format.
"""

import struct
from .types import EFieldTypes


class DbWriter:
    """Writes bit-compressed integers, floats, and strings to a byte buffer."""

    def __init__(self):
        self._buffer = bytearray()
        self._current_byte = 0
        self._bit_pos = 0  # 0-7, next bit position within current_byte

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_integer(self, value: int, depth: int, range_low: int = 0):
        """Write an integer field: clamp to valid range, subtract range_low."""
        raw = value - range_low
        max_val = (1 << depth) - 1
        raw = max(0, min(raw, max_val))
        self._write_bits(raw, depth)

    def write_float(self, value: float):
        """Write a 4-byte IEEE 754 float (little-endian, byte-aligned)."""
        self._align_to_byte()
        self._buffer.extend(struct.pack("<f", value))

    def write_string(self, value: str, max_bytes: int):
        """Write a UTF-8 string, null-terminated if room, zero-padded to max_bytes."""
        self._align_to_byte()
        encoded = value.encode("utf-8")
        if len(encoded) >= max_bytes:
            # String fills the entire field — no room for null terminator
            self._buffer.extend(encoded[:max_bytes])
        else:
            # Room for null terminator
            self._buffer.extend(encoded)
            self._buffer.append(0)  # null terminator
            remaining = max_bytes - len(encoded) - 1
            if remaining > 0:
                self._buffer.extend(b"\x00" * remaining)

    def write_raw_bytes(self, data: bytes):
        """Write raw bytes directly (byte-aligned)."""
        self._align_to_byte()
        self._buffer.extend(data)

    def align_to_byte(self):
        """Pad remaining bits in current byte with zeros."""
        self._align_to_byte()

    def to_bytes(self) -> bytes:
        """Flush and return the complete byte buffer."""
        self._flush()
        return bytes(self._buffer)

    @property
    def bit_position(self) -> int:
        """Current absolute bit position in the output."""
        return len(self._buffer) * 8 + self._bit_pos

    def byte_count(self) -> int:
        """Return number of bytes written so far (excluding unflushed bits)."""
        return len(self._buffer)

    # ------------------------------------------------------------------
    # Internal bit-level operations
    # ------------------------------------------------------------------

    def _write_bits(self, value: int, depth: int):
        """Write `depth` bits LSB-first, little-endian byte order.

        This is the inverse of DbReader.read_bits().
        """
        remaining = depth
        while remaining > 0:
            if self._bit_pos >= 8:
                self._buffer.append(self._current_byte)
                self._current_byte = 0
                self._bit_pos = 0

            bits_in_byte = min(8 - self._bit_pos, remaining)
            # Extract lowest bits_in_byte bits
            byte_val = value & ((1 << bits_in_byte) - 1)
            self._current_byte |= (byte_val << self._bit_pos)
            value >>= bits_in_byte
            self._bit_pos += bits_in_byte
            remaining -= bits_in_byte

    def _align_to_byte(self):
        """Skip remaining bits to reach next byte boundary."""
        if self._bit_pos > 0:
            self._buffer.append(self._current_byte)
            self._current_byte = 0
            self._bit_pos = 0

    def _flush(self):
        """Ensure all bits are written to the buffer."""
        if self._bit_pos > 0:
            self._buffer.append(self._current_byte)
            self._current_byte = 0
            self._bit_pos = 0
