import unittest

from core.config import find_latest_save
from web_app import EditorState, create_app


SAMPLE = find_latest_save()


@unittest.skipUnless(SAMPLE and SAMPLE.is_file(), "本机没有 FC26 样本存档")
class QuickFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = EditorState(SAMPLE, remember_path=False)
        cls.client = create_app(cls.state).test_client()
        cls.headers = {"X-Editor-Token": cls.state.token}

    def tearDown(self):
        self.state.reset()

    def test_age18_requires_token_and_stages_all_players(self):
        self.assertEqual(
            self.client.post("/api/quick/age18", json={}).status_code,
            403,
        )
        response = self.client.post(
            "/api/quick/age18",
            headers=self.headers,
            json={},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertGreater(result["players_updated"], 0)
        self.assertEqual(
            {record.get("birthdate") for record in self.state.players.table.records},
            {155123},
        )

    def test_add_missing_legends_is_staged_and_idempotent(self):
        preview = self.client.get("/api/quick/legends").get_json()
        self.assertGreater(preview["missing_count"], 0)
        response = self.client.post(
            "/api/quick/add-legends",
            headers=self.headers,
            json={},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["added"], preview["missing_count"])
        self.assertEqual(self.client.get("/api/quick/legends").get_json()["missing_count"], 0)
        self.assertEqual(
            self.client.post(
                "/api/quick/add-legends",
                headers=self.headers,
                json={},
            ).get_json()["added"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
