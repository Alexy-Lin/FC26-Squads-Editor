"""SavFile — FC26 squad save container (FBCHUNKS wrapper + embedded DB).

FC26 FBCHUNKS header is ~1178 bytes (vs 146 in FIFA19), with a different
DataSize offset formula.  This module handles both load and save."""

import struct
from pathlib import Path
from typing import Optional
from .db_file import DbFile
from .meta_parser import MetaDatabase


# Derive the FBCHUNKS header DataSize correction from the source file.
#   FIFA19:   total - DataSize = 102   (18-byte prefix + 84-byte trailer)
#   FC26:     total - DataSize = 1126  (verified from real save)
FC26_DATASIZE_DIFF = 1126


class SavFile:
    """FC26 squad save file (.sav container)."""

    DB_MAGIC = b"DB\x00\x08"

    def __init__(self):
        self.fbchunks_header: bytes = b""
        self.db: Optional[DbFile] = None
        self.filepath: Optional[Path] = None

    def load(self, filepath: Path, meta_db: Optional[MetaDatabase] = None):
        """Load an FC26 .sav file."""
        self.filepath = Path(filepath)

        with open(filepath, "rb") as f:
            data = f.read()

        # Find the embedded DB signature (dynamic offset)
        db_pos = data.find(self.DB_MAGIC)
        if db_pos == -1:
            raise ValueError(
                f"Not a valid FC26 save file: DB signature not found in {filepath}"
            )

        self.fbchunks_header = data[:db_pos]

        self.db = DbFile()
        self.db.load(data[db_pos:], meta_db)

    def save(self, filepath: Optional[Path] = None) -> Path:
        """Save the DB back to a .sav file, preserving FBCHUNKS header."""
        if self.db is None:
            raise ValueError("No DB loaded — nothing to save.")

        output_path = Path(filepath) if filepath else self.filepath
        if output_path is None:
            raise ValueError("No output path specified.")

        db_data = self.db.save()

        # Prepare FBCHUNKS header
        fbchunks = bytearray(self.fbchunks_header)

        # 1) Zero mystery hash bytes after "SaveType_Squads\0" suffix.
        #    Game stores a hash there that becomes stale when DB changes.
        save_type_pos = fbchunks.find(b"SaveType_Squads")
        if save_type_pos >= 0:
            mystery_start = save_type_pos + 16  # "SaveType_Squads" + \0
            for i in range(mystery_start, mystery_start + 8):
                if i < len(fbchunks):
                    fbchunks[i] = 0

        # 2) Update DataSize at bytes 14-17 (little-endian uint32).
        #    Verified formula for FC 26:  DataSize = total_file_size - 1126
        total_size = len(fbchunks) + len(db_data)
        new_data_size = total_size - FC26_DATASIZE_DIFF
        fbchunks[14:18] = struct.pack("<I", new_data_size)

        # Write: FBCHUNKS header + DB data
        with open(output_path, "wb") as f:
            f.write(bytes(fbchunks))
            f.write(db_data)

        return output_path

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"FC26 Save File: {self.filepath}",
            f"  FBCHUNKS header: {len(self.fbchunks_header)} bytes",
            "",
        ]
        if self.db:
            lines.append(self.db.summary())
        return "\n".join(lines)
