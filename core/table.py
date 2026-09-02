"""Table — parses a single DB table: header, field descriptors, and records."""

import struct
from typing import List, Optional, Dict, Any
from .db_reader import DbReader
from .db_writer import DbWriter
from .field_descriptor import FieldDescriptor
from .meta_parser import MetaDatabase, MetaTable
from .types import EFieldTypes


def _compute_crc(data: bytes) -> int:
    """Compute FIFA DB CRC-32 (poly 0x04C11DB7, init 0xFFFFFFFF, no final XOR).

    This is CRC-32/MPEG-2 — non-reflected, MSB-first processing.
    """
    # Precomputed table for polynomial 0x04C11DB7 (non-reflected)
    table = [
        0x00000000, 0x04C11DB7, 0x09823B6E, 0x0D4326D9,
        0x130476DC, 0x17C56B6B, 0x1A864DB2, 0x1E475005,
        0x2608EDB8, 0x22C9F00F, 0x2F8AD6D6, 0x2B4BCB61,
        0x350C9B64, 0x31CD86D3, 0x3C8EA00A, 0x384FBDBD,
        0x4C11DB70, 0x48D0C6C7, 0x4593E01E, 0x4152FDA9,
        0x5F15ADAC, 0x5BD4B01B, 0x569796C2, 0x52568B75,
        0x6A1936C8, 0x6ED82B7F, 0x639B0DA6, 0x675A1011,
        0x791D4014, 0x7DDC5DA3, 0x709F7B7A, 0x745E66CD,
        0x9823B6E0, 0x9CE2AB57, 0x91A18D8E, 0x95609039,
        0x8B27C03C, 0x8FE6DD8B, 0x82A5FB52, 0x8664E6E5,
        0xBE2B5B58, 0xBAEA46EF, 0xB7A96036, 0xB3687D81,
        0xAD2F2D84, 0xA9EE3033, 0xA4AD16EA, 0xA06C0B5D,
        0xD4326D90, 0xD0F37027, 0xDDB056FE, 0xD9714B49,
        0xC7361B4C, 0xC3F706FB, 0xCEB42022, 0xCA753D95,
        0xF23A8028, 0xF6FB9D9F, 0xFBB8BB46, 0xFF79A6F1,
        0xE13EF6F4, 0xE5FFEB43, 0xE8BCCD9A, 0xEC7DD02D,
        0x34867077, 0x30476DC0, 0x3D044B19, 0x39C556AE,
        0x278206AB, 0x23431B1C, 0x2E003DC5, 0x2AC12072,
        0x128E9DCF, 0x164F8078, 0x1B0CA6A1, 0x1FCDBB16,
        0x018AEB13, 0x054BF6A4, 0x0808D07D, 0x0CC9CDCA,
        0x7897AB07, 0x7C56B6B0, 0x71159069, 0x75D48DDE,
        0x6B93DDDB, 0x6F52C06C, 0x6211E6B5, 0x66D0FB02,
        0x5E9F46BF, 0x5A5E5B08, 0x571D7DD1, 0x53DC6066,
        0x4D9B3063, 0x495A2DD4, 0x44190B0D, 0x40D816BA,
        0xACA5C697, 0xA864DB20, 0xA527FDF9, 0xA1E6E04E,
        0xBFA1B04B, 0xBB60ADFC, 0xB6238B25, 0xB2E29692,
        0x8AAD2B2F, 0x8E6C3698, 0x832F1041, 0x87EE0DF6,
        0x99A95DF3, 0x9D684044, 0x902B669D, 0x94EA7B2A,
        0xE0B41DE7, 0xE4750050, 0xE9362689, 0xEDF73B3E,
        0xF3B06B3B, 0xF771768C, 0xFA325055, 0xFEF34DE2,
        0xC6BCF05F, 0xC27DEDE8, 0xCF3ECB31, 0xCBFFD686,
        0xD5B88683, 0xD1799B34, 0xDC3ABDED, 0xD8FBA05A,
        0x690CE0EE, 0x6DCDFD59, 0x608EDB80, 0x644FC637,
        0x7A089632, 0x7EC98B85, 0x738AAD5C, 0x774BB0EB,
        0x4F040D56, 0x4BC510E1, 0x46863638, 0x42472B8F,
        0x5C007B8A, 0x58C1663D, 0x558240E4, 0x51435D53,
        0x251D3B9E, 0x21DC2629, 0x2C9F00F0, 0x285E1D47,
        0x36194D42, 0x32D850F5, 0x3F9B762C, 0x3B5A6B9B,
        0x0315D626, 0x07D4CB91, 0x0A97ED48, 0x0E56F0FF,
        0x1011A0FA, 0x14D0BD4D, 0x19939B94, 0x1D528623,
        0xF12F560E, 0xF5EE4BB9, 0xF8AD6D60, 0xFC6C70D7,
        0xE22B20D2, 0xE6EA3D65, 0xEBA91BBC, 0xEF68060B,
        0xD727BBB6, 0xD3E6A601, 0xDEA580D8, 0xDA649D6F,
        0xC423CD6A, 0xC0E2D0DD, 0xCDA1F604, 0xC960EBB3,
        0xBD3E8D7E, 0xB9FF90C9, 0xB4BCB610, 0xB07DABA7,
        0xAE3AFBA2, 0xAAFBE615, 0xA7B8C0CC, 0xA379DD7B,
        0x9B3660C6, 0x9FF77D71, 0x92B45BA8, 0x9675461F,
        0x8832161A, 0x8CF30BAD, 0x81B02D74, 0x857130C3,
        0x5D8A9099, 0x594B8D2E, 0x5408ABF7, 0x50C9B640,
        0x4E8EE645, 0x4A4FFBF2, 0x470CDD2B, 0x43CDC09C,
        0x7B827D21, 0x7F436096, 0x7200464F, 0x76C15BF8,
        0x68860BFD, 0x6C47164A, 0x61043093, 0x65C52D24,
        0x119B4BE9, 0x155A565E, 0x18197087, 0x1CD86D30,
        0x029F3D35, 0x065E2082, 0x0B1D065B, 0x0FDC1BEC,
        0x3793A651, 0x3352BBE6, 0x3E119D3F, 0x3AD08088,
        0x2497D08D, 0x2056CD3A, 0x2D15EBE3, 0x29D4F654,
        0xC5A92679, 0xC1683BCE, 0xCC2B1D17, 0xC8EA00A0,
        0xD6AD50A5, 0xD26C4D12, 0xDF2F6BCB, 0xDBEE767C,
        0xE3A1CBC1, 0xE760D676, 0xEA23F0AF, 0xEEE2ED18,
        0xF0A5BD1D, 0xF464A0AA, 0xF9278673, 0xFDE69BC4,
        0x89B8FD09, 0x8D79E0BE, 0x803AC667, 0x84FBDBD0,
        0x9ABC8BD5, 0x9E7D9662, 0x933EB0BB, 0x97FFAD0C,
        0xAFB010B1, 0xAB710D06, 0xA6322BDF, 0xA2F33668,
        0xBCB4666D, 0xB8757BDA, 0xB5365D03, 0xB1F740B4,
    ]
    crc = 0xFFFFFFFF
    for byte in data:
        crc = ((crc << 8) ^ table[((crc >> 24) ^ byte) & 0xFF]) & 0xFFFFFFFF
    return crc


class Table:
    """A single database table with its field descriptors and records."""

    def __init__(self, short_name: str = ""):
        self.short_name: str = short_name
        self.long_name: str = ""
        self.fields: List[FieldDescriptor] = []
        self._fields_sorted: List[FieldDescriptor] = []  # sorted by bit_offset for reading
        self._fields_by_short: Dict[str, FieldDescriptor] = {}
        self._fields_by_name: Dict[str, FieldDescriptor] = {}
        self._field_descriptors_raw: bytes = b""  # raw bytes for writing back unchanged

        # Header fields
        self.unknown00: int = 0
        self.record_size: int = 0       # bytes per record (byte-aligned size)
        self.n_bit_records: int = 0
        self.compressed_string_length: int = 0
        self.n_records: int = 0         # total slots
        self.n_valid_records: int = 0   # used slots
        self.unknown14: int = 0
        self.n_fields: int = 0
        self._field_count_raw: int = 0  # uint32 at offset 24 (= n_fields + 0x100 in all observed tables)
        self.unknown1c: int = 0
        self.crc_table_header: int = 0

        # Records data position/bookkeeping
        self._records_byte_start: int = 0
        self._raw_records_data: bytes = b""  # raw bytes for ALL record slots (valid + empty/deleted)
        self._compressed_string_data: bytes = b""
        self._trailing_data: bytes = b""  # records CRC + table metadata after compressed strings
        # end byte position in the original binary (after trailing data)
        self._end_byte: int = 0
        self._original_n_valid_records: int = 0  # snapshot after load, before any additions

        # Parsed records (only valid ones)
        self.records: List[Dict[str, Any]] = []

    def load(self, reader: DbReader, meta_db: Optional[MetaDatabase] = None):
        """Load table from binary reader at current position."""
        # -- Read table header (36 bytes) --
        self.unknown00 = struct.unpack("<I", reader.read_bytes(4))[0]
        self.record_size = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_bit_records = struct.unpack("<I", reader.read_bytes(4))[0]
        self.compressed_string_length = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_records = struct.unpack("<H", reader.read_bytes(2))[0]
        self.n_valid_records = struct.unpack("<H", reader.read_bytes(2))[0]
        self.unknown14 = struct.unpack("<i", reader.read_bytes(4))[0]
        # Bytes 24-27: uint32 = n_fields + 0x100 (NOT 1 byte + 3 padding)
        field_count_raw = struct.unpack("<I", reader.read_bytes(4))[0]
        self.n_fields = field_count_raw & 0xFF
        self._field_count_raw = field_count_raw
        self.unknown1c = struct.unpack("<I", reader.read_bytes(4))[0]
        self.crc_table_header = struct.unpack("<I", reader.read_bytes(4))[0]

        # -- Read field descriptors (preserve raw bytes + original order) --
        fd_start = reader.position
        self.fields = []
        for i in range(self.n_fields):
            fd = FieldDescriptor(index=i)
            fd.load(reader)
            self.fields.append(fd)
            self._fields_by_short[fd.short_name_str] = fd
        fd_end = reader.position
        self._field_descriptors_raw = reader._data[fd_start:fd_end]

        # -- Apply XML metadata --
        if meta_db:
            mt = meta_db.get_table(self.short_name)
            if mt:
                self.long_name = mt.name
                for fd in self.fields:
                    mf = mt.fields.get(fd.short_name_str)
                    if mf:
                        fd.apply_xml_metadata(mf.name, mf.range_low, mf.range_high)
                        self._fields_by_name[mf.name] = fd

        # Keep sorted copy for reading, but preserve original field order
        self._fields_sorted = sorted(self.fields, key=lambda f: f.bit_offset)

        # -- Record where record data begins --
        self._records_byte_start = reader.position

        # -- Read records --
        self.records = []
        for rec_idx in range(self.n_valid_records):
            record = self._read_record(reader, rec_idx)
            if record is not None:
                self.records.append(record)

        # Capture raw record data (including deleted/empty slots — may contain non-zero data)
        records_total_size = self.n_records * self.record_size
        self._raw_records_data = reader._data[
            self._records_byte_start : self._records_byte_start + records_total_size
        ]

        # Snapshot original valid record count (used by save() for in-place overlay)
        self._original_n_valid_records = self.n_valid_records

        # Advance reader position past all record slots (including deleted)
        records_end = self._records_byte_start + records_total_size
        reader.position = records_end

        # Skip compressed string data if present
        if self.compressed_string_length > 0:
            self._compressed_string_data = reader.read_bytes(self.compressed_string_length)

        # Record end position (for trailing data extraction by DbFile)
        self._end_byte = reader.position

    def _read_record(self, reader: DbReader, rec_idx: int) -> Optional[Dict[str, Any]]:
        """Read a single record using sorted field descriptors."""
        record_start_byte = self._records_byte_start + rec_idx * self.record_size
        record = {}

        for fd in self._fields_sorted:
            abs_bit = record_start_byte * 8 + fd.bit_offset
            reader.seek_to_bit(abs_bit)

            if fd.field_type == EFieldTypes.Integer:
                value = reader.read_integer(fd.depth, fd.range_low)
            elif fd.field_type == EFieldTypes.Float:
                value = reader.read_float()
            elif fd.field_type == EFieldTypes.String:
                str_len = fd.depth // 8
                value = reader.read_string(str_len)
            elif fd.field_type in (
                EFieldTypes.ShortCompressedString,
                EFieldTypes.LongCompressedString,
            ):
                value = reader.read_integer(32, 0)
            else:
                value = None

            record[fd.field_name or fd.short_name_str] = value

        return record

    def save(self) -> bytes:
        """Serialize the table back to binary format (RDBM-verified format).

        Key changes from the original game format:
          - field_count_raw = n_fields   (not n_fields + 0x100)
          - Table header CRC recomputed  (covers header bytes 0-31)
          - Trailing CRC = _compute_crc(FD + records + compressed_str)
          - Record overlay preserves original padding bits

        The game uses CRC-32/MPEG-2 (_compute_crc) to verify ALL CRCs
        when field_count_raw equals just n_fields.
        """
        writer = DbWriter()

        # -- Table header (36 bytes, CRC=0 placeholder) --
        writer.write_raw_bytes(struct.pack("<I", self.unknown00))
        writer.write_raw_bytes(struct.pack("<I", self.record_size))
        writer.write_raw_bytes(struct.pack("<I", self.n_bit_records))
        writer.write_raw_bytes(struct.pack("<I", self.compressed_string_length))
        writer.write_raw_bytes(struct.pack("<H", self.n_records))
        writer.write_raw_bytes(struct.pack("<H", self.n_valid_records))
        writer.write_raw_bytes(struct.pack("<i", self.unknown14))
        # RDBM format: write just n_fields, not n_fields + 0x100
        writer.write_raw_bytes(struct.pack("<I", self.n_fields))
        writer.write_raw_bytes(struct.pack("<I", self.unknown1c))
        writer.write_raw_bytes(struct.pack("<I", 0))  # CRC placeholder

        # -- Field descriptors (in original file order) --
        for fd in self.fields:
            writer.write_raw_bytes(struct.pack("<i", int(fd.field_type)))
            writer.write_raw_bytes(struct.pack("<i", fd.bit_offset))
            writer.write_raw_bytes(fd.short_name)
            writer.write_raw_bytes(struct.pack("<i", fd.depth))

        # -- Records: overlay field values onto original bytes (preserve padding) --
        sorted_fields = sorted(self.fields, key=lambda f: f.bit_offset)
        valid_size = self.n_valid_records * self.record_size
        for rec_idx in range(self.n_valid_records):
            record = self.records[rec_idx]
            if rec_idx < self._original_n_valid_records:
                # Overlay fields onto original bytes (preserves padding/bits)
                orig_start = rec_idx * self.record_size
                orig_bytes = self._raw_records_data[orig_start:orig_start + self.record_size]
                rec_bytes = self._write_record(record, sorted_fields, orig_bytes)
            else:
                # New records: encode from scratch, zero-pad
                rec_bytes = self._write_record(record, sorted_fields)
                if len(rec_bytes) < self.record_size:
                    rec_bytes += b"\x00" * (self.record_size - len(rec_bytes))
                elif len(rec_bytes) > self.record_size:
                    rec_bytes = rec_bytes[:self.record_size]
            writer.write_raw_bytes(rec_bytes)

        # Preserve original data for deleted/empty slots
        if len(self._raw_records_data) > valid_size:
            writer.write_raw_bytes(self._raw_records_data[valid_size:])

        # -- Compressed string data (preserve original) --
        if self.compressed_string_length > 0:
            writer.write_raw_bytes(self._compressed_string_data)

        table_data = writer.to_bytes()

        # -- Compute and patch table header CRC: covers bytes 0-31 --
        header_crc = _compute_crc(table_data[:32])
        table_data = table_data[:32] + struct.pack("<I", header_crc) + table_data[36:]

        # -- Compute and patch trailing CRC: covers FD + records + compressed_str --
        content = table_data[36:]
        records_crc = _compute_crc(content)

        # RDBM trailing format: 4-byte CRC only (no metadata padding).
        # When field_count_raw = n_fields (no 0x100 flag), the game uses standard
        # CRC-32/MPEG-2 and expects only the 4-byte CRC as trailing data, not the
        # game-native metadata footer.
        # Preserve original trailing bytes after the CRC to maintain file size.
        new_trailing = struct.pack("<I", records_crc)
        if len(self._trailing_data) > 4:
            new_trailing += self._trailing_data[4:]  # skip old CRC, keep rest

        table_data += new_trailing
        return table_data

    def _write_record(self, record: Dict[str, Any],
                      sorted_fields: List[FieldDescriptor],
                      original_bytes: bytes = b"") -> bytes:
        """Encode a single record's fields using DbWriter.

        Field bits are overlaid onto *original_bytes*, preserving any
        padding bits that lie beyond the last defined field.  This ensures
        that re-serialising an unmodified record produces exactly the
        original bytes, which is required for CRC tables whose algorithm
        cannot be reproduced by _compute_crc.
        """
        rw = DbWriter()
        for fd in sorted_fields:
            key = fd.field_name or fd.short_name_str
            value = record.get(key, 0)

            if fd.field_type == EFieldTypes.Integer:
                rw.write_integer(value, fd.depth, fd.range_low)
            elif fd.field_type == EFieldTypes.Float:
                rw.write_float(value)
            elif fd.field_type == EFieldTypes.String:
                str_len = fd.depth // 8
                rw.write_string(str(value) if value else "", str_len)
            elif fd.field_type in (
                EFieldTypes.ShortCompressedString,
                EFieldTypes.LongCompressedString,
            ):
                rw.write_integer(value, 32, 0)
            else:
                rw.write_integer(0, fd.depth, 0)

        field_bytes = rw.to_bytes()

        if original_bytes and len(original_bytes) >= self.record_size:
            # Overlay field bits onto original bytes, preserving padding
            result = bytearray(original_bytes[:self.record_size])
            # Compute last field's end bit to identify the boundary
            last_end = max((fd.bit_offset + fd.depth) for fd in sorted_fields) if sorted_fields else 0
            last_byte = last_end // 8            # byte index of the last field bit
            padding_start_bit = last_end % 8      # first *padding* bit within that byte

            # Full field bytes: bytes 0 .. last_byte-1 get the complete computed value
            for i in range(min(last_byte, len(field_bytes))):
                result[i] = field_bytes[i]

            # Partial byte (if any): keep field bits from computed, padding from original
            if last_byte < self.record_size and last_byte < len(field_bytes):
                mask = (1 << padding_start_bit) - 1   # bits [0..padding_start_bit-1] = field
                result[last_byte] = (
                    (field_bytes[last_byte] & mask)
                    | (original_bytes[last_byte] & ~mask)
                )
            # Bytes beyond last_byte are pure padding — already preserved from original
            return bytes(result)

        # No original bytes — pad with zeros
        if len(field_bytes) < self.record_size:
            field_bytes += b"\x00" * (self.record_size - len(field_bytes))
        elif len(field_bytes) > self.record_size:
            field_bytes = field_bytes[:self.record_size]
        return field_bytes

    # ------------------------------------------------------------------
    # Field lookups
    # ------------------------------------------------------------------

    def get_field(self, short_name: str) -> Optional[FieldDescriptor]:
        """Look up a field descriptor by short name."""
        return self._fields_by_short.get(short_name)

    def get_field_by_name(self, name: str) -> Optional[FieldDescriptor]:
        """Look up a field descriptor by full name."""
        return self._fields_by_name.get(name)

    def __repr__(self):
        n_fields = len(self.fields)
        n_recs = len(self.records)
        return (
            f"Table('{self.long_name or self.short_name}', "
            f"{n_fields} fields, {n_recs} records, "
            f"recordSize={self.record_size}B)"
        )
