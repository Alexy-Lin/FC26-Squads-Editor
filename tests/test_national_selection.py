import copy
import unittest

from core.config import find_latest_save
from web_app import EditorState, create_app


SAMPLE = find_latest_save()


@unittest.skipUnless(SAMPLE and SAMPLE.is_file(), "本机没有 FC26 样本存档")
class NationalSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = EditorState(SAMPLE, remember_path=False)
        cls.client = create_app(cls.state).test_client()
        cls.headers = {"X-Editor-Token": cls.state.token}
        response = cls.client.get("/api/national-teams/1369")
        if response.status_code != 200 or response.get_json().get("roster_size") != 26:
            raise unittest.SkipTest("样本存档没有完整的 FC26 26 人国家队名单")

    def tearDown(self):
        self.state.reset()

    def test_read_and_authorization(self):
        team = self.client.get("/api/national-teams/1369").get_json()
        self.assertTrue(team["editable"])
        self.assertEqual(len(team["roster"]), 26)
        self.assertGreater(len(team["candidates"]), 26)
        self.assertEqual(self.client.get("/api/national-teams/47").status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/national-teams/1369",
                json={"roster": []},
            ).status_code,
            403,
        )

    def test_selection_is_staged_and_invalid_request_is_atomic(self):
        team = self.client.get("/api/national-teams/1369").get_json()
        selected = {item["playerid"] for item in team["roster"]}
        incoming = next(
            item
            for item in team["candidates"]
            if item["playerid"] not in selected and not item["unavailable"]
        )
        roster = [
            {"playerid": item["playerid"], "jerseynumber": index + 1}
            for index, item in enumerate(team["roster"])
        ]
        outgoing = roster[0]["playerid"]
        roster[0]["playerid"] = incoming["playerid"]

        response = self.client.post(
            "/api/national-teams/1369",
            json={"roster": roster},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual({change.table for change in self.state.changes.values()}, {"RrqT"})
        self.assertEqual(
            self.client.post(
                "/api/national-teams/1369",
                json={"roster": roster},
                headers=self.headers,
            ).get_json()["applied"],
            0,
        )

        self.state.reset()
        before = copy.deepcopy(self.state.rosters.table.records)
        response = self.client.post(
            "/api/national-teams/1369",
            json={"roster": roster[:-1]},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.state.rosters.table.records, before)
        self.assertFalse(self.state.changes)


if __name__ == "__main__":
    unittest.main()
