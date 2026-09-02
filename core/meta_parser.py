"""Parse fifa_ng_db-meta.xml to map table/field short names to human-readable info."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional


class MetaField:
    """XML field definition."""
    __slots__ = ("name", "short_name", "field_type", "depth",
                 "range_high", "range_low", "is_key", "is_update")

    def __init__(self):
        self.name: str = ""
        self.short_name: str = ""
        self.field_type: str = ""
        self.depth: int = 0
        self.range_high: int = 0
        self.range_low: int = 0
        self.is_key: bool = False
        self.is_update: bool = False


class MetaTable:
    """XML table definition."""
    __slots__ = ("name", "short_name", "fields", "savegroups")

    def __init__(self):
        self.name: str = ""
        self.short_name: str = ""
        self.fields: Dict[str, MetaField] = {}  # keyed by short_name
        self.savegroups: str = ""


class MetaDatabase:
    """Parsed fifa_ng_db-meta.xml."""

    def __init__(self):
        self.tables: Dict[str, MetaTable] = {}  # keyed by table short_name

    @classmethod
    def from_file(cls, path: Path) -> "MetaDatabase":
        """Parse the meta XML file."""
        db = cls()
        tree = ET.parse(str(path))
        root = tree.getroot()

        for table_el in root.findall("table"):
            mt = MetaTable()
            mt.name = table_el.get("name", "")
            mt.short_name = table_el.get("shortname", "")
            mt.savegroups = table_el.get("savegroups", "")

            for field_el in table_el.findall(".//field"):
                mf = MetaField()
                mf.name = field_el.get("name", "")
                mf.short_name = field_el.get("shortname", "")
                mf.field_type = field_el.get("type", "")
                mf.depth = int(field_el.get("depth", "0"))
                mf.range_high = int(field_el.get("rangehigh", "0"))
                mf.range_low = int(field_el.get("rangelow", "0"))
                mf.is_key = field_el.get("key", "False").lower() == "true"
                mf.is_update = field_el.get("update", "False").lower() == "true"
                mt.fields[mf.short_name] = mf

            if mt.short_name:
                db.tables[mt.short_name] = mt

        return db

    def get_table(self, short_name: str) -> Optional[MetaTable]:
        """Look up table metadata by short name."""
        return self.tables.get(short_name)

    def get_field(self, table_short: str, field_short: str) -> Optional[MetaField]:
        """Look up field metadata."""
        mt = self.tables.get(table_short)
        if mt:
            return mt.fields.get(field_short)
        return None
