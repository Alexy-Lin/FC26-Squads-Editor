import unittest

from core.config import find_latest_save
from services.birthdates import BIRTHDATE_MIN, REAL_BIRTHDAYS
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

    def _birthdates(self):
        return {
            record.get("playerid"): record.get("birthdate")
            for record in self.state.players.table.records
        }

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

    def test_restore_original_birthdays_undoes_age18(self):
        before = self._birthdates()
        self.client.post("/api/quick/age18", headers=self.headers, json={})

        status = self.client.get("/api/quick/birthdates").get_json()
        self.assertTrue(status["available"])
        self.assertGreater(status["restore_count"], 0)

        response = self.client.post(
            "/api/quick/restore-birthdays",
            headers=self.headers,
            json={},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertGreater(response.get_json()["players_updated"], 0)
        self.assertEqual(self._birthdates(), before)
        self.assertEqual(
            self.client.post("/api/quick/restore-birthdays", json={}).status_code,
            403,
        )

    def _remove_one_male_legend(self):
        """临时移除一名在档的男足传奇，用来验证"添加缺失传奇"。"""
        preview = self.client.get("/api/quick/legends").get_json()
        self.assertGreater(preview["present_count"], 0)
        player_id = preview["present_sample"][0]["playerid"]
        players = self.state.sav.db.get_table("CZUM")
        links = self.state.sav.db.get_table("RrqT")
        players.records[:] = [r for r in players.records if r.get("playerid") != player_id]
        links.records[:] = [r for r in links.records if r.get("playerid") != player_id]
        players.n_valid_records = len(players.records)
        links.n_valid_records = len(links.records)
        return player_id

    def test_legend_catalog_excludes_women(self):
        preview = self.client.get("/api/quick/legends").get_json()
        self.assertFalse(preview["include_women"])
        self.assertGreater(preview["women_skipped_count"], 0)
        for item in preview["missing"] + preview["present_sample"]:
            self.assertEqual(item.get("gender"), 0)
        skipped_ids = {item["playerid"] for item in preview["women_skipped"]}
        self.assertIn(275243, skipped_ids)          # Mia Hamm
        self.assertNotIn(275243, {i["playerid"] for i in preview["missing"]})

    def test_legend_catalog_includes_kempes_and_rivellino(self):
        preview = self.client.get("/api/quick/legends").get_json()
        extra_ids = {item["playerid"] for item in preview["extras"]}
        self.assertIn(82092, extra_ids)
        self.assertIn(191190, extra_ids)
        self.assertTrue(all(item["available"] for item in preview["extras"]))
        # 导入时必须使用合法生日，否则游戏会隐藏该球员
        self.assertEqual(REAL_BIRTHDAYS[82092], 135779)
        self.assertEqual(REAL_BIRTHDAYS[191190], 132662)
        for item in preview["missing"] + preview["extras"]:
            self.assertGreaterEqual(item.get("birthdate", BIRTHDATE_MIN), BIRTHDATE_MIN)

    def test_add_missing_legends_is_staged_and_idempotent(self):
        removed = self._remove_one_male_legend()
        preview = self.client.get("/api/quick/legends").get_json()
        missing_ids = {item["playerid"] for item in preview["missing"]}
        self.assertIn(removed, missing_ids)
        response = self.client.post(
            "/api/quick/add-legends",
            headers=self.headers,
            json={},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["added"], preview["missing_count"])
        self.assertIn(removed, {item["playerid"] for item in result["legends"]})
        self.assertEqual(self.client.get("/api/quick/legends").get_json()["missing_count"], 0)
        self.assertEqual(
            self.client.post(
                "/api/quick/add-legends",
                headers=self.headers,
                json={},
            ).get_json()["added"],
            0,
        )

    def test_added_legends_use_real_birthdates_and_get_names(self):
        self._remove_one_male_legend()
        preview = self.client.get("/api/quick/legends").get_json()
        self.client.post("/api/quick/add-legends", headers=self.headers, json={})
        added_ids = {item["playerid"] for item in preview["missing"]}
        records = {
            record.get("playerid"): record
            for record in self.state.players.table.records
            if record.get("playerid") in added_ids
        }
        self.assertEqual(set(records), added_ids)
        for player_id, record in records.items():
            self.assertGreaterEqual(record.get("birthdate", 0), BIRTHDATE_MIN)
            if player_id in REAL_BIRTHDAYS:
                self.assertEqual(record.get("birthdate"), REAL_BIRTHDAYS[player_id])
        names_table = self.state.sav.db.get_table("nQVU")
        if names_table:
            names = {record.get("playerid") for record in names_table.records}
            for item in preview["missing"]:
                if item.get("name_record"):
                    self.assertIn(item["playerid"], names)

    def test_peak_restore_requires_token_and_never_lowers_ratings(self):
        self.assertEqual(self.client.post("/api/quick/peak", json={}).status_code, 403)

        preview = self.client.get("/api/quick/peak").get_json()
        self.assertIn("count", preview)
        self.assertIn("candidates", preview)

        # 让测试与存档状态无关：把一名已知候选人的能力值压回低点，再恢复。
        candidate_id = 20801  # Cristiano Ronaldo，FIFA19 巅峰 94
        records = {record.get("playerid"): record for record in self.state.players.table.records}
        target = records.get(candidate_id)
        if target is None:
            self.skipTest("当前存档里没有测试用的候选人")
        original_ovr = target.get("overallrating")
        target["overallrating"] = 70
        target["finishing"] = 60
        try:
            preview = self.client.get("/api/quick/peak").get_json()
            found = {item["playerid"] for item in preview["candidates"]}
            self.assertIn(candidate_id, found)
            peak = next(item for item in preview["candidates"] if item["playerid"] == candidate_id)
            self.assertEqual(peak["peak"], 94)
            self.assertEqual(peak["overallrating"], 70)

            before = {
                record.get("playerid"): record.get("overallrating", 0)
                for record in self.state.players.table.records
            }
            before[candidate_id] = 70
            response = self.client.post(
                "/api/quick/peak",
                headers=self.headers,
                json={"only_raise": True},
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            result = response.get_json()
            self.assertEqual(result["restored_count"], result["candidate_count"])
            self.assertTrue(result["only_raise"])
            self.assertEqual(target.get("overallrating"), 94)
            self.assertGreater(target.get("finishing"), 60)
            for record in self.state.players.table.records:
                player_id = record.get("playerid")
                self.assertGreaterEqual(
                    record.get("overallrating", 0),
                    before.get(player_id, 0),
                    f"{player_id} 的能力值被降低了",
                )
            for item in result["restored"]:
                self.assertGreaterEqual(item["overallrating_after"], item["overallrating"])
        finally:
            if original_ovr is not None:
                target["overallrating"] = original_ovr

    def test_attribute_gap_is_restored_when_overall_already_matches_peak(self):
        """德佩那种情况：OVR 已经到巅峰，但单项属性仍然偏低。"""
        candidate_id = 20801  # Cristiano Ronaldo
        records = {record.get("playerid"): record for record in self.state.players.table.records}
        target = records.get(candidate_id)
        if target is None:
            self.skipTest("当前存档里没有测试用的候选人")
        original = (target.get("overallrating"), target.get("aggression"), target.get("potential"))
        target["aggression"] = 1  # 只有单项属性偏低，OVR 不变
        try:
            preview = self.client.get("/api/quick/peak").get_json()
            found = {item["playerid"]: item for item in preview["candidates"]}
            self.assertIn(candidate_id, found)
            self.assertEqual(found[candidate_id]["overallrating"], original[0])
            self.assertEqual(found[candidate_id]["gain"], 0)
            self.assertGreaterEqual(found[candidate_id]["raiseable"], 1)

            result = self.client.post(
                "/api/quick/peak", headers=self.headers, json={"only_raise": True}
            ).get_json()
            self.assertGreater(result["restored_count"], 0)
            self.assertGreater(target.get("aggression"), 1)
            self.assertEqual(target.get("overallrating"), original[0])
        finally:
            target["aggression"] = original[1]
            if original[2] is not None:
                target["potential"] = original[2]
            if original[0] is not None:
                target["overallrating"] = original[0]

    def test_goalkeeper_attributes_are_part_of_the_peak_table(self):
        from services.peak_service import PeakRestoreService

        service = PeakRestoreService(self.state.sav)
        for field in service.GK_FIELDS:
            self.assertIn(field, service.FIELDS)
        self.assertIn("aggression", service.FIELDS)
        self.assertIn("defensiveawareness", service.FIELDS)

    def test_legend_dialog_returns_the_full_list(self):
        """「查看名单」按钮用 scope=all 拿到完整名单（含已拥有的）。"""
        data = self.client.get("/api/quick/legends?scope=all").get_json()
        self.assertEqual(len(data["available"]), data["available_count"])
        self.assertEqual(
            data["present_count"] + data["missing_count"],
            data["available_count"],
        )
        ids = {item["playerid"] for item in data["available"]}
        self.assertIn(82092, ids)     # Kempes
        self.assertIn(191190, ids)    # Rivellino
        for item in data["available"]:
            self.assertIn("birthdate_source", item)
            self.assertEqual(item["gender"], 0)
        # 待添加的必须排在前面
        flags = [item["missing"] for item in data["available"]]
        self.assertEqual(flags, sorted(flags, reverse=True))

    def test_peak_dialog_returns_the_full_roster(self):
        """「查看名单」按钮用 include_done=1 拿到全部在册老将（含已达标）。"""
        data = self.client.get("/api/quick/peak?include_done=1").get_json()
        self.assertGreaterEqual(data["roster_count"], 1)
        self.assertEqual(len(data["candidates"]), data["roster_count"])
        self.assertEqual(data["count"], sum(1 for item in data["candidates"] if not item["done"]))
        for item in data["candidates"]:
            self.assertIn("raiseable", item)
            self.assertIn("club", item)
        # 待恢复的排在前面
        flags = [item["done"] for item in data["candidates"]]
        self.assertEqual(flags, sorted(flags))
        # 默认（不传 include_done）只返回待恢复的
        plain = self.client.get("/api/quick/peak").get_json()
        self.assertEqual(plain["count"], sum(1 for item in plain["candidates"] if not item["done"]))
        self.assertTrue(all(not item["done"] for item in plain["candidates"]))


if __name__ == "__main__":
    unittest.main()
