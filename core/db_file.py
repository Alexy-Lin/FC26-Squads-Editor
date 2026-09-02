"""DbFile — the DB container (header + table directory + tables)."""

import struct
import zlib
from typing import Dict, Optional, BinaryIO, List
from pathlib import Path
from .db_reader import DbReader
from .db_writer import DbWriter
from .table import Table, _compute_crc
from .meta_parser import MetaDatabase


class DbFile:
    """FC26 DB file container — header, table directory, and all tables."""

    MAGIC = b"DB\x00\x08"

    def __init__(self):
        self.platform: int = 0  # 0=PC, 1=Xbox
        self.file_length: int = 0
        self.reserved: int = 0
        self.n_tables: int = 0
        self.crc_header: int = 0
        self.crc_short_names: int = 0

        # keyed by table short name
        self.tables: Dict[str, Table] = {}

        # Raw directory entries (short_name -> offset pairs)
        self._table_offsets: Dict[str, int] = {}

        # Original table order (list of short names in directory order)
        self._table_order: List[str] = []

    def load(self, data: bytes, meta_db: Optional[MetaDatabase] = None):
        """Load DB from raw byte data."""
        reader = DbReader(data)

        # -- DB Header (24 bytes) --
        magic = reader.read_bytes(4)
        if magic != self.MAGIC:
            raise ValueError(
                f"Invalid DB magic: {magic!r}, expected {self.MAGIC!r}"
            )
        self.platform = reader.read_bytes(1)[0]
        reader.read_bytes(3)  # padding
        self.file_length = struct.unpack("<I", reader.read_bytes(4))[0]
        self.reserved = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_tables = struct.unpack("<I", reader.read_bytes(4))[0]
        self.crc_header = struct.unpack("<I", reader.read_bytes(4))[0]

        # -- Table Directory --
        self._table_order = []
        for _ in range(self.n_tables):
            name_bytes = reader.read_bytes(4)
            name = name_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
            offset = struct.unpack("<I", reader.read_bytes(4))[0]
            if name:
                self._table_order.append(name)
                self._table_offsets[name] = offset

        # ShortNames CRC
        self.crc_short_names = struct.unpack("<I", reader.read_bytes(4))[0]

        # Data section starts here
        data_section_start = reader.position

        # Calculate sorted table offsets for boundary checking
        table_offset_pairs = [(name, self._table_offsets.get(name, 0))
                              for name in self._table_order]
        table_offset_pairs.sort(key=lambda x: x[1])

        # -- Load Tables --
        for i, (name, table_offset) in enumerate(table_offset_pairs):
            abs_offset = data_section_start + table_offset
            reader.position = abs_offset

            table = Table(short_name=name)
            table.load(reader, meta_db)
            self.tables[name] = table

            # Calculate trailing data: bytes between this table's end and next table's start
            if i + 1 < len(table_offset_pairs):
                next_abs_offset = data_section_start + table_offset_pairs[i + 1][1]
            else:
                next_abs_offset = len(data)

            trailing_start = table._end_byte
            trailing_size = next_abs_offset - trailing_start
            if trailing_size > 0:
                table._trailing_data = data[trailing_start:next_abs_offset]
            else:
                table._trailing_data = b""

    def save(self) -> bytes:
        """Serialize the complete DB back to binary.

        Produces: DB header + table directory + short names CRC + table data
        """
        writer = DbWriter()

        # -- DB Header (24 bytes) with CRC placeholder --
        writer.write_raw_bytes(self.MAGIC)                        # 0-3: magic
        writer.write_raw_bytes(bytes([self.platform]))            # 4: platform
        writer.write_raw_bytes(b"\x00\x00\x00")                   # 5-7: padding
        writer.write_raw_bytes(struct.pack("<I", self.file_length))  # 8-11: file length (placeholder)
        writer.write_raw_bytes(struct.pack("<I", self.reserved))     # 12-15: reserved
        writer.write_raw_bytes(struct.pack("<I", self.n_tables))     # 16-19: n_tables
        writer.write_raw_bytes(struct.pack("<I", 0))              # 20-23: CRC placeholder

        # -- Table directory + short names CRC placeholder --
        table_dir_start = writer.byte_count()
        for name in self._table_order:
            # Short name (4 bytes, null-padded)
            name_bytes = name.encode("ascii").ljust(4, b"\x00")[:4]
            writer.write_raw_bytes(name_bytes)
            # Offset placeholder (will be updated after data section is built)
            writer.write_raw_bytes(struct.pack("<I", 0))
        table_dir_end = writer.byte_count()

        writer.write_raw_bytes(struct.pack("<I", 0))  # short names CRC placeholder

        # -- Data section: serialize each table --
        data_section_start = writer.byte_count()
        table_offsets: Dict[str, int] = {}

        for name in self._table_order:
            table = self.tables.get(name)
            if table is None:
                continue

            # Calculate offset from data section start
            current_offset = writer.byte_count() - data_section_start
            table_offsets[name] = current_offset

            # Save table data
            table_data = table.save()
            writer.write_raw_bytes(table_data)

        # -- Now patch everything --
        full_data = bytearray(writer.to_bytes())

        # 1) Patch table directory offsets
        dir_entry_size = 8
        for i, name in enumerate(self._table_order):
            entry_offset = table_dir_start + i * dir_entry_size
            offset_bytes = struct.pack("<I", table_offsets.get(name, 0))
            full_data[entry_offset + 4 : entry_offset + 8] = offset_bytes

        # 2) Update file_length (must be before CRC computation!)
        file_length = len(full_data)
        full_data[8:12] = struct.pack("<I", file_length)

        # 3) Compute and patch header CRC: covers bytes 0-19 (before CRC field)
        header_crc = _compute_crc(bytes(full_data[:20]))
        full_data[20:24] = struct.pack("<I", header_crc)

        # 4) Compute and patch short names CRC: covers table directory entries
        dir_bytes = bytes(full_data[table_dir_start:table_dir_end])
        short_names_crc = _compute_crc(dir_bytes)
        sn_crc_pos = table_dir_end
        full_data[sn_crc_pos : sn_crc_pos + 4] = struct.pack("<I", short_names_crc)

        return bytes(full_data)

    # ------------------------------------------------------------------
    # Load utilities
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: Path, meta_db: Optional[MetaDatabase] = None) -> "DbFile":
        """Load a raw DB file from disk (not a .sav wrapper)."""
        with open(path, "rb") as f:
            data = f.read()
        db = cls()
        db.load(data, meta_db)
        return db

    def get_table(self, short_name: str) -> Optional[Table]:
        return self.tables.get(short_name)

    def get_table_by_name(self, long_name: str) -> Optional[Table]:
        for table in self.tables.values():
            if table.long_name == long_name:
                return table
        return None

    def summary(self) -> str:
        """Return a human-readable summary of all tables."""
        lines = [
            f"DB File: {self.n_tables} tables",
            f"  Platform: {'PC' if self.platform == 0 else 'Xbox'}",
            f"  File length (header): {self.file_length:,}",
            f"  CRC Header: 0x{self.crc_header:08X}",
            f"  CRC ShortNames: 0x{self.crc_short_names:08X}",
            "",
        ]
        for name, table in self.tables.items():
            lines.append(
                f"  {name:6s}  {table.long_name:<35s}  "
                f"{len(table.fields):3d} fields  "
                f"{table.n_valid_records:5d}/{table.n_records:5d} records  "
                f"({table.record_size}B each)"
            )
        return "\n".join(lines)
