import struct
import tempfile
import unittest
from pathlib import Path

from core.meta_parser import MetaDatabase
from core.config import find_latest_save
from core.sav_file import FC26_DATASIZE_DIFF, SavFile
from services.player_service import PlayerService
from services.save_service import SafeSaveService


ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "fifa_ng_db-meta.xml"
SAMPLE = find_latest_save()


@unittest.skipUnless(SAMPLE.is_file(), "本机没有 FC26 样本存档")
class SaveRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = MetaDatabase.from_file(META)

    def test_player_edit_round_trip_preserves_container_size(self):
        sav = SavFile()
        sav.load(SAMPLE, self.meta)
        player = PlayerService(sav)
        before = player.get_player(158023)["overallrating"]
        target = 99 if before != 99 else 98
        changes = player.update_fields(158023, {"overallrating": str(target)})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "SquadsRoundTrip"
            result = SafeSaveService(self.meta).save(sav, changes, output_path=output)
            data = result.path.read_bytes()
            self.assertEqual(len(data), SAMPLE.stat().st_size)
            self.assertEqual(struct.unpack_from("<I", data, 14)[0], len(data) - FC26_DATASIZE_DIFF)
            loaded = SavFile()
            loaded.load(output, self.meta)
            self.assertEqual(loaded.db.get_table("CZUM").records[0].__class__, dict)
            after = PlayerService(loaded).get_player(158023)["overallrating"]
            self.assertNotEqual(before, after)
            self.assertEqual(after, target)
