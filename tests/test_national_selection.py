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

    def test_candidates_match_roster_gender_and_skip_placeholders(self):
        """英格兰候补里不该出现女足球员和 5v5/Rush 占位球员。"""
        response = self.client.get("/api/national-teams/1318")
        if response.status_code != 200:
            self.skipTest("当前存档没有英格兰国家队")
        team = response.get_json()
        self.assertEqual(team["gender"], 0)
        ids = {item["playerid"] for item in team["candidates"]}
        for player_id in (258980, 227246, 246426):     # Alessia Russo / Lucy Bronze / Leah Williamson
            self.assertNotIn(player_id, ids, f"{player_id} 是女足球员，不应出现在男足候补里")
        for player_id in (70846, 70847):               # Rush Goalkeeper（5 对 5 球队）
            self.assertNotIn(player_id, ids, f"{player_id} 是 Rush 占位球员")
        self.assertIn(204935, ids)                     # J. Pickford 应该在
        players = {record.get("playerid"): record for record in self.state.players.table.records}
        for item in team["candidates"]:
            self.assertEqual((players[item["playerid"]].get("gender") or 0), team["gender"])

    def test_placeholder_player_ids_only_cover_small_sided_rosters(self):
        from services.national_service import NationalService

        service = NationalService(self.state.rosters)
        placeholders = service.placeholder_player_ids()
        self.assertTrue({70846, 70847}.issubset(placeholders))
        for player_id in (204935, 158023, 20801):      # 真实球员不得被误判
            self.assertNotIn(player_id, placeholders)

    def test_national_team_list_includes_teams_found_in_the_save(self):
        """日本/韩国/摩洛哥/女足队等应出现在国家队列表里，且不再算俱乐部。"""
        options = self.client.get("/api/meta").get_json()
        national = {item["teamid"] for item in options["national_teams"]}
        clubs = {item["teamid"] for item in options["clubs"]}
        for team_id in (1411, 974, 111111, 113002):    # 日本 / 韩国 / 摩洛哥 / 英格兰女足
            self.assertIn(team_id, national)
            self.assertNotIn(team_id, clubs, f"{team_id} 是国家队，不该出现在俱乐部列表里")
        for team_id in (1, 48):                        # 阿森纳 / 那不勒斯仍是俱乐部
            self.assertIn(team_id, clubs)
            self.assertNotIn(team_id, national)
        self.assertNotIn(131524, national)             # 5 对 5 球队不是国家队

    def test_womens_team_offers_women_and_keeps_its_own_size(self):
        response = self.client.get("/api/national-teams/113002")   # 英格兰女足
        if response.status_code != 200:
            self.skipTest("当前存档没有英格兰女足")
        team = response.get_json()
        self.assertEqual(team["gender"], 1)
        self.assertEqual(team["expected_roster_size"], team["roster_size"])
        self.assertTrue(team["editable"])
        ids = {item["playerid"] for item in team["candidates"]}
        self.assertIn(258980, ids)          # Alessia Russo
        self.assertNotIn(204935, ids)       # J. Pickford 是男足

    def test_detected_national_teams_does_not_swallow_clubs(self):
        from services.national_service import NationalService

        service = NationalService(self.state.rosters)
        resolver = self.state.resolver
        detected = resolver.detected_national_teams()
        self.assertEqual(detected & {1, 48, 131524}, set())
        # 检测结果应与“CxJp + 国家名 + 名单国籍一致”一致，且幂等
        self.assertEqual(detected, resolver.detected_national_teams())
        self.assertIsInstance(service.roster_gender([]), int)


    def test_womens_team_selection_keeps_its_23_records(self):
        """女足队名单 23 人，原位选拔后记录数不变。"""
        team = self.client.get("/api/national-teams/113002").get_json()
        if not team.get("editable"):
            self.skipTest("当前存档没有可编辑的英格兰女足")
        links = [
            record for record in self.state.rosters.table.records
            if record.get("teamid") == 113002
        ]
        before = len(links)
        self.assertEqual(team["expected_roster_size"], before)
        selected = {item["playerid"] for item in team["roster"]}
        incoming = next(
            item for item in team["candidates"]
            if item["playerid"] not in selected and not item["unavailable"]
        )
        roster = [
            {"playerid": item["playerid"], "jerseynumber": index + 1}
            for index, item in enumerate(team["roster"])
        ]
        roster[0]["playerid"] = incoming["playerid"]
        response = self.client.post(
            "/api/national-teams/113002",
            json={"roster": roster},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        after = [
            record for record in self.state.rosters.table.records
            if record.get("teamid") == 113002
        ]
        self.assertEqual(len(after), before)
        self.assertEqual({change.table for change in self.state.changes.values()}, {"RrqT"})
        # 少一个人必须被拒绝
        rejected = self.client.post(
            "/api/national-teams/113002",
            json={"roster": roster[:-1]},
            headers=self.headers,
        )
        self.assertEqual(rejected.status_code, 400)


    def test_team_options_carry_gender_and_mark_womens_teams(self):
        """男足/女足按钮依赖 team_options 的 gender 字段与「· 女足」标签。"""
        options = self.client.get("/api/meta").get_json()
        national = {item["teamid"]: item for item in options["national_teams"]}
        men = [item for item in national.values() if item["gender"] == 0]
        women = [item for item in national.values() if item["gender"] == 1]
        self.assertTrue(men)
        self.assertTrue(women)
        for item in women:
            self.assertIn("女足", item["label"])
        for item in men:
            self.assertNotIn("女足", item["label"])
        self.assertEqual(national[1318]["gender"], 0)      # 英格兰男足
        self.assertEqual(national[113002]["gender"], 1)    # 英格兰女足
        self.assertNotEqual(national[1318]["label"], national[113002]["label"])

    def test_candidates_carry_position_for_auto_numbering(self):
        """自动编号需要候选球员的位置与能力，前端才有数据可算。"""
        team = self.client.get("/api/national-teams/1318").get_json()
        self.assertTrue(team["candidates"])
        for item in team["candidates"][:200]:
            self.assertIn("position", item)
            self.assertIn("overallrating", item)
            self.assertIsInstance(item["primary_position"], str)
        keeper = next(
            (item for item in team["candidates"] if item["primary_position"] == "GK"),
            None,
        )
        self.assertIsNotNone(keeper)
        self.assertEqual(keeper["position"], 0)

    def test_manager_and_placeholder_records_are_not_candidates(self):
        """自由球员经理（第二个齐达内）与 Rush 占位球员都不能当国家队候选。"""
        team = self.client.get("/api/national-teams/1335").get_json()   # 法国男足
        if team.get("nation_id") != 18:
            self.skipTest("当前存档没有法国男足")
        ids = {item["playerid"] for item in team["candidates"]}
        self.assertNotIn(238399, ids)     # 经理版 Zinedine Zidane（自由球员经理）
        self.assertIn(1397, ids)          # ICON 版 Zinedine Zidane
        self.assertGreaterEqual(team["excluded_placeholders"], 1)
        resolver = self.state.resolver
        self.assertTrue(resolver.is_non_player_team(131680))   # 自由球员经理
        self.assertFalse(resolver.is_non_player_team(111592))  # 自由球员池保留
        self.assertFalse(resolver.is_non_player_team(1))       # 阿森纳

    def test_transfer_team_list_hides_placeholder_pools(self):
        options = self.client.get("/api/meta").get_json()
        clubs = {item["teamid"] for item in options["clubs"]}
        self.assertIn(111592, clubs)                            # 自由球员池保留
        for item in options["clubs"]:
            self.assertFalse(
                self.state.resolver.is_non_player_team(item["teamid"]),
                f"{item['label']} 是占位/经理池，不该出现在转会球队列表里",
            )


if __name__ == "__main__":
    unittest.main()
