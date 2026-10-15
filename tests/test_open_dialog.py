import unittest
from pathlib import Path

import core.file_dialog as file_dialog
from core.config import find_latest_save
from web_app import EditorState, create_app


SAMPLE = find_latest_save()


@unittest.skipUnless(SAMPLE and SAMPLE.is_file(), "本机没有 FC26 样本存档")
class OpenSaveDialogTests(unittest.TestCase):
    """「打开存档」按钮走系统文件选择窗口（后端弹窗），不再要求手填路径。"""

    @classmethod
    def setUpClass(cls):
        cls.state = EditorState(SAMPLE, remember_path=False)
        cls.client = create_app(cls.state).test_client()
        cls.headers = {"X-Editor-Token": cls.state.token}

    def tearDown(self):
        self.state.reset()

    def _patch_picker(self, replacement):
        original = file_dialog.pick_file
        file_dialog.pick_file = replacement
        return original

    def test_pick_save_requires_token(self):
        self.assertEqual(self.client.post("/api/pick-save", json={}).status_code, 403)

    def test_pick_save_returns_the_dialog_choice(self):
        original = self._patch_picker(lambda *a, **k: SAMPLE)
        try:
            response = self.client.post("/api/pick-save", headers=self.headers, json={})
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            self.assertFalse(data["cancelled"])
            self.assertEqual(data["path"], str(SAMPLE))
            self.assertEqual(data["name"], SAMPLE.name)
        finally:
            file_dialog.pick_file = original

    def test_pick_save_reports_cancel(self):
        original = self._patch_picker(lambda *a, **k: None)
        try:
            data = self.client.post("/api/pick-save", headers=self.headers, json={}).get_json()
            self.assertTrue(data["cancelled"])
            self.assertNotIn("path", data)
        finally:
            file_dialog.pick_file = original

    def test_pick_save_survives_a_dialog_failure(self):
        def boom(*args, **kwargs):
            raise RuntimeError("没有可用的图形界面")

        original = self._patch_picker(boom)
        try:
            data = self.client.post("/api/pick-save", headers=self.headers, json={}).get_json()
            self.assertIn("error", data)
            self.assertFalse(data["cancelled"])
        finally:
            file_dialog.pick_file = original

    def test_open_by_filename_resolves_inside_the_settings_folder(self):
        data = self.client.post(
            "/api/open", headers=self.headers, json={"filename": SAMPLE.name}
        ).get_json()
        self.assertEqual(data["save_name"], SAMPLE.name)
        missing = self.client.post(
            "/api/open", headers=self.headers, json={"filename": "绝对不存在的存档名"}
        )
        self.assertEqual(missing.status_code, 400)
        self.assertIn("找不到", missing.get_json()["error"])

    def test_open_by_path_still_works(self):
        data = self.client.post(
            "/api/open", headers=self.headers, json={"path": str(SAMPLE)}
        ).get_json()
        self.assertEqual(data["save_name"], SAMPLE.name)

    def test_default_save_dir_points_at_the_fc26_settings_folder(self):
        directory = file_dialog.default_save_dir()
        self.assertIsNotNone(directory)
        self.assertTrue(Path(directory).is_dir())
        self.assertIn("EA SPORTS FC 26", str(directory))


if __name__ == "__main__":
    unittest.main()
