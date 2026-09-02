"""FC26 DB field type enums and constants."""

from enum import IntEnum

DB_MAGIC = b"DB\x00\x08"
FBCHUNKS_MAGIC = b"FBCHUNKS"


class EFieldTypes(IntEnum):
    String = 0
    Integer = 3
    Float = 4
    ShortCompressedString = 13
    LongCompressedString = 14


# Table header field count
TABLE_HEADER_SIZE = 36  # 9 fields (4+4+4+4+2+2+4+1+3+4+4) = 36 bytes before field descriptors
