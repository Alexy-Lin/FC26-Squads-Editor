import datetime
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from core.meta_parser import MetaDatabase
from core.sav_file import FC26_DATASIZE_DIFF, SavFile
from .changes import FieldChange, RecordChange


@dataclass(frozen=True)
class SaveResult:
    path: Path
    table_count: int
    verified_changes: int


class SafeSaveService:
    """Save to a new file, then reload it and verify every requested change."""

    def __init__(self, meta_db: MetaDatabase):
        self.meta_db = meta_db

    def save(
        self,
        sav: SavFile,
        changes: Iterable[FieldChange] = (),
        output_dir: Optional[Path] = None,
        output_path: Optional[Path] = None,
    ) -> SaveResult:
        if not sav.db or not sav.filepath:
            raise ValueError("存档尚未加载")
        changes = list(changes)
        target_dir = Path(output_dir) if output_dir else sav.filepath.parent
        if not target_dir.is_dir():
            raise ValueError(f"输出目录不存在：{target_dir}")
        destination = Path(output_path) if output_path else self._next_path(target_dir)
        if destination.resolve() == sav.filepath.resolve():
            raise ValueError("安全保存禁止覆盖输入存档，请使用新的输出文件")
        if destination.exists():
            raise ValueError(f"输出文件已存在，为避免覆盖请换一个路径：{destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        counts_before = {name: len(table.records) for name, table in sav.db.tables.items()}
        handle = tempfile.NamedTemporaryFile(prefix=".fc26-save-", suffix=".tmp", dir=destination.parent, delete=False)
        temporary = Path(handle.name)
        handle.close()
        try:
            sav.save(temporary)
            loaded = SavFile()
            loaded.load(temporary, self.meta_db)
            self._validate_container(temporary)
            self._validate_counts(counts_before, loaded)
            self._validate_changes(changes, loaded)
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return SaveResult(destination, len(counts_before), len(changes))

    @staticmethod
    def _next_path(directory: Path) -> Path:
        now = datetime.datetime.now().replace(microsecond=0)
        for offset in range(86400):
            stamp = (now + datetime.timedelta(seconds=offset)).strftime("%Y%m%d%H%M%S")
            candidate = directory / f"Squads{stamp}"
            if not candidate.exists():
                return candidate
        raise RuntimeError("无法生成可用的时间戳存档名")

    @staticmethod
    def _validate_container(path: Path):
        data = path.read_bytes()
        if not data.startswith(b"FBCHUNKS"):
            raise ValueError("保存验证失败：FBCHUNKS 头无效")
        if len(data) < 18:
            raise ValueError("保存验证失败：文件过短")
        data_size = struct.unpack_from("<I", data, 14)[0]
        if data_size != len(data) - FC26_DATASIZE_DIFF:
            raise ValueError("保存验证失败：FC26 FBCHUNKS DataSize 不匹配")
        save_type_pos = data.find(b"SaveType_Squads\x00")
        if save_type_pos < 0 or data[save_type_pos + 16:save_type_pos + 24] != b"\x00" * 8:
            raise ValueError("保存验证失败：FC26 FBCHUNKS 校验字节未归零")
        if data.find(b"DB\x00\x08") < 0:
            raise ValueError("保存验证失败：DB 容器不存在")

    @staticmethod
    def _validate_counts(counts_before, loaded: SavFile):
        if not loaded.db:
            raise ValueError("保存验证失败：DB 未能重载")
        counts_after = {name: len(table.records) for name, table in loaded.db.tables.items()}
        if counts_after != counts_before:
            raise ValueError("保存验证失败：表或有效记录数量发生意外变化")

    @staticmethod
    def _validate_changes(changes, loaded: SavFile):
        for change in changes:
            table = loaded.db.get_table(change.table)
            if not table:
                raise ValueError(f"保存验证失败：缺少表 {change.table}")
            record = next((r for r in table.records if r.get(change.key_field) == change.key_value), None)
            if isinstance(change, RecordChange):
                continue
            if record is None or record.get(change.field) != change.new_value:
                raise ValueError(f"保存验证失败：{change.table}.{change.field} 未正确写入")
