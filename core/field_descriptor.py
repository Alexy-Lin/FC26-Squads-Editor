"""Field descriptor — metadata for a single field in a table."""

import struct
from .db_reader import DbReader
from .types import EFieldTypes


class FieldDescriptor:
    """Describes a single field in a DB table record."""

    __slots__ = (
        "field_type", "bit_offset", "short_name", "short_name_str",
        "depth", "range_low", "range_high", "field_name",
        "_original_index",
    )

    def __init__(self, index: int = 0):
        self.field_type: EFieldTypes = EFieldTypes.Integer
        self.bit_offset: int = 0
        self.short_name: bytes = b"\x00\x00\x00\x00"
        self.short_name_str: str = ""
        self.depth: int = 0
        self.range_low: int = 0
        self.range_high: int = 0
        self.field_name: str = ""
        self._original_index: int = index

    def load(self, reader: DbReader):
        """Read field descriptor from binary (16 bytes)."""
        type_val = struct.unpack("<I", reader.read_bytes(4))[0]
        self.field_type = EFieldTypes(type_val)

        self.bit_offset = struct.unpack("<I", reader.read_bytes(4))[0]
        self.short_name = reader.read_bytes(4)
        self.short_name_str = self.short_name.rstrip(b"\x00").decode(
            "ascii", errors="replace"
        )
        self.depth = struct.unpack("<I", reader.read_bytes(4))[0]

    def set_original_index(self, index: int):
        """Set the original field order index (for writing back)."""
        self._original_index = index

    def apply_xml_metadata(self, name: str, range_low: int, range_high: int):
        """Apply field metadata from XML schema."""
        self.field_name = name
        self.range_low = range_low
        self.range_high = range_high

    @property
    def is_key(self) -> bool:
        """Check if this is the primary key field (heuristically)."""
        return self.short_name_str in ("ykFq", "mCXg", "oHkj", "LhXN", "uipx", "fwCQ")

    def __repr__(self):
        return (
            f"FD({self.field_name or self.short_name_str}, "
            f"type={self.field_type.name}, depth={self.depth}, "
            f"bitOff={self.bit_offset}, range=[{self.range_low}, {self.range_high}])"
        )
