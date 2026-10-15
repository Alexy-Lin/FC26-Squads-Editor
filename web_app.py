"""FC26 save editor Web application.

The browser is only a client.  All binary parsing and writes happen in this
process, and writes are staged in memory until the user explicitly saves.
"""

import argparse
import secrets
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from core.config import choose_startup_save, find_save_candidates, load as load_config, save as save_config
from core.mappings import ATTRIBUTE_CATEGORIES, NATIONS_CN, OPTION_MAPS, POSITION_NAMES
from core.meta_parser import MetaDatabase
from core.name_resolver import NameResolver
from core.sav_file import SavFile
from core.traits import FC26_TRAIT1, FC26_TRAIT2
from services.changes import ChangeSet, FieldChange, RecordChange
from services.legend_service import LegendService
from services.national_service import NationalService
from services.peak_service import PeakRestoreService
from services.player_service import PlayerService
from services.quick_service import QuickFeatureService
from services.roster_service import RosterService
from services.save_service import SafeSaveService
from services.team_service import TeamService


APP_ROOT = Path(__file__).resolve().parent
WEB_ROOT = APP_ROOT / "web"
HEADS_ROOT = APP_ROOT / "data" / "heads"
META_PATH = APP_ROOT / "data" / "fifa_ng_db-meta.xml"


def as_bool(value, default=False):
    """Parse a boolean coming from JSON or a query string ("1"/"true"/"yes"/"all")."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "yes", "on", "all")


class EditorState:
    def __init__(self, startup_path=None, remember_path=True):
        self.meta = MetaDatabase.from_file(META_PATH)
        self.remember_path = remember_path
        self.sav = SavFile()
        self.changes = {}
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(24)
        self.resolver = None
        self.players = None
        self.rosters = None
        self.teams = None
        self.player_index = []
        config = load_config()
        selected = Path(startup_path) if startup_path else choose_startup_save(
            config.get("last_save_path"), APP_ROOT / "testdata"
        )[0]
        if selected:
            self.load(selected)

    def _rebuild_indexes(self):
        """Recreate table services and name/team indexes after record additions."""
        self.resolver = NameResolver(self.sav.db)
        self.players = PlayerService(self.sav)
        self.rosters = RosterService(self.sav)
        self.teams = TeamService(self.sav)
        self.player_index = []
        for record in self.players.table.records:
            player_id = record.get("playerid", 0)
            if player_id <= 0:
                continue
            self.player_index.append((
                record,
                self.resolver.get_name(record),
                self.resolver.get_name_cn(record),
            ))

    def load(self, path):
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"找不到存档：{path}")
        sav = SavFile()
        sav.load(path, self.meta)
        self.sav = sav
        self.changes.clear()
        self._rebuild_indexes()
        if self.remember_path:
            save_config({"last_save_path": str(path.resolve())})
        self._log(f"已加载存档 {path.name}，球员 {len(self.player_index)} 人")

    def summary(self):
        return {
            "loaded": bool(self.sav.db),
            "save_path": str(self.sav.filepath) if self.sav.filepath else "",
            "save_name": self.sav.filepath.name if self.sav.filepath else "",
            "player_count": len(self.player_index),
            "pending_changes": len(self.changes),
            "token": self.token,
        }

    def pick_save_path(self):
        """Open the native file dialog (Explorer) and return the chosen save."""
        from core.file_dialog import default_save_dir, pick_file, tk_available, win32_available

        directory = default_save_dir()
        try:
            chosen = pick_file(initial_dir=directory)
        except Exception as exc:  # pragma: no cover - dialog backends are defensive
            return {"error": f"无法打开系统文件选择窗口：{exc}", "cancelled": False,
                    "start_dir": str(directory or "")}
        if not chosen:
            return {"cancelled": True, "start_dir": str(directory or "")}
        path = Path(chosen)
        if not path.is_file():
            return {"error": f"找不到存档：{path}", "cancelled": False}
        self._log(f"通过系统文件选择窗口选中 {path.name}")
        return {"path": str(path), "name": path.name, "cancelled": False,
                "start_dir": str(directory or ""),
                "dialog_backends": {"win32": win32_available(), "tk": tk_available()}}

    def load_by_filename(self, filename):
        """Resolve a save by name inside the known FC26 settings folders."""
        name = Path(str(filename or "")).name
        if not name:
            raise ValueError("没有提供存档文件名")
        candidates = find_save_candidates()
        match = next((item for item in candidates if item.name == name), None)
        if match is None:
            raise ValueError(
                f"在 FC26 存档目录里找不到 {name}（共 {len(candidates)} 个候选存档）"
            )
        self.load(match)
        return self.summary()

    def _log(self, message):
        if self.remember_path:
            print(f"[操作] {message}", flush=True)

    def _log_changes(self, label, changes):
        details = []
        for change in changes:
            if isinstance(change, FieldChange):
                details.append(f"{change.table}.{change.field} {change.old_value}->{change.new_value}")
            elif isinstance(change, RecordChange):
                details.append(f"{change.table} {change.action} {change.key_field}={change.key_value}")
        self._log(f"{label}：{', '.join(details[:6]) or '无字段变化'}")

    @staticmethod
    def _int_query(query, key, default=0):
        raw = query.get(key, [""])[0].strip()
        return int(raw) if raw else default

    def search_players(self, query):
        if not self.players:
            return []
        text = query.get("q", [""])[0].strip().casefold()
        nation = query.get("nation", [""])[0].strip().casefold()
        position_raw = query.get("position", [""])[0].strip()
        position = int(position_raw) if position_raw else None
        minimum = self._int_query(query, "min_overall", 0)
        limit = max(1, min(self._int_query(query, "limit", 100), 300))
        if not text and not nation and position is None and not minimum:
            limit = min(limit, 40)
        results = []
        for record, name, name_cn in self.player_index:
            player_id = record.get("playerid", 0)
            if text and text not in name.casefold() and text not in name_cn.casefold() and text not in str(player_id):
                continue
            nation_id = record.get("nationality", 0)
            nation_text = f"{NATIONS_CN.get(nation_id, '')} {self.resolver.get_nation_name(nation_id)} {nation_id}".casefold()
            if nation and nation not in nation_text:
                continue
            if position is not None and record.get("preferredposition1") != position:
                continue
            overall = record.get("overallrating", 0) or 0
            if minimum and overall < minimum:
                continue
            club, national = self.resolver.get_player_team(player_id)
            club_id, national_id = self.resolver.get_player_team_ids(player_id)
            results.append({
                "playerid": player_id,
                "name": name,
                "name_cn": name_cn,
                "overallrating": overall,
                "potential": record.get("potential", 0),
                "position": POSITION_NAMES.get(record.get("preferredposition1"), str(record.get("preferredposition1", ""))),
                "nation": NATIONS_CN.get(nation_id, self.resolver.get_nation_name(nation_id)),
                "club": club or "",
                "club_id": club_id,
                "national_team": national or "",
                "national_team_id": national_id,
            })
        results.sort(key=lambda item: (item["overallrating"] or 0, item["playerid"]), reverse=True)
        return results[:limit]

    def player_detail(self, player_id):
        record = self.players.get_player(player_id)
        fields = []
        option_maps = dict(OPTION_MAPS)
        nations = dict(NATIONS_CN)
        for code, name in self.resolver.get_nations().items():
            nations.setdefault(code, name)
        option_maps["nationality"] = nations
        for category, items in ATTRIBUTE_CATEGORIES:
            category_fields = []
            for field_name, label in items:
                fd = self.players.table.get_field_by_name(field_name)
                if not fd:
                    continue
                options = option_maps.get(field_name)
                category_fields.append({
                    "name": field_name,
                    "label": label,
                    "value": record.get(field_name, fd.range_low),
                    "type": fd.field_type.name,
                    "min": fd.range_low,
                    "max": fd.range_high,
                    "read_only": field_name == "playerid",
                    "options": [
                        {"value": value, "label": text}
                        for value, text in sorted(options.items(), key=lambda item: item[0])
                    ] if options else [],
                })
            if category_fields:
                fields.append({"name": category, "fields": category_fields})
        club_link = self.rosters.current_team_link(player_id, False)
        national_link = self.rosters.current_team_link(player_id, True)
        head = HEADS_ROOT / f"p{player_id}.png"
        return {
            "playerid": player_id,
            "name": self.resolver.get_name(record),
            "name_cn": self.resolver.get_name_cn(record),
            "common_name": self.resolver.get_common_name(record),
            "head": f"/heads/p{player_id}.png" if head.is_file() else "",
            "fields": fields,
            "traits": self._trait_details(record),
            "club": self._team_value(club_link, False),
            "national_team": self._team_value(national_link, True),
        }

    @staticmethod
    def _trait_details(record):
        def items(mapping, value, icon=False):
            result = []
            for bit, name in mapping:
                local_bit = bit - 30 if mapping is FC26_TRAIT2 else bit
                result.append({
                    "bank": 2 if mapping is FC26_TRAIT2 else 1,
                    "bit": bit,
                    "name": ("图标 " if icon else "") + name,
                    "enabled": bool((value or 0) & (1 << local_bit)),
                    "icon": icon,
                })
            return result

        return {
            "regular": items(FC26_TRAIT1, record.get("trait1")),
            "regular2": items(FC26_TRAIT2, record.get("trait2")),
            "icon": items(FC26_TRAIT1, record.get("icontrait1"), True),
            "icon2": items(FC26_TRAIT2, record.get("icontrait2"), True),
        }

    def update_trait(self, player_id, body):
        try:
            bank = int(body["bank"])
            bit = int(body["bit"])
            enabled = bool(body.get("enabled"))
            icon = bool(body.get("icon"))
        except (KeyError, TypeError, ValueError):
            raise ValueError("特性修改必须包含有效的 bank、bit 和 enabled")
        change = self.players.set_trait(player_id, bank, bit, enabled, icon)
        changes = ChangeSet()
        if change:
            changes.add(change)
            self._record_changes(changes)
        return {"applied": len(changes), "pending_changes": len(self.changes)}

    def _team_value(self, record, national):
        if not record:
            return {"teamid": None, "label": "" if national else "自由球员"}
        team_id = record.get("teamid")
        item = next((item for item in self.rosters.team_options(national) if item["teamid"] == team_id), None)
        return {"teamid": team_id, "label": item["label"] if item else self.resolver.get_team_name(team_id)}

    def update_player(self, player_id, body):
        changes = ChangeSet()
        try:
            updates = {key: str(value) for key, value in body.get("fields", {}).items()}
            changes.extend(self.players.update_fields(player_id, updates))
            for key, national in (("national_team", True), ("club", False)):
                if key not in body:
                    continue
                value = body[key]
                target = int(value) if isinstance(value, int) or str(value).strip().isdigit() else self.rosters.resolve_team(str(value), national)
                changes.extend(self.rosters.replace_team(player_id, target, national))
        except Exception:
            changes.rollback(self.sav)
            raise
        self.resolver.refresh_player_teams(self.rosters.table)
        self.players.resolver.refresh_player_teams(self.rosters.table)
        self.teams.resolver.refresh_player_teams(self.rosters.table)
        self._record_changes(changes)
        self._log_changes(f"球员 {player_id} 修改", changes)
        return {"applied": len(changes), "pending_changes": len(self.changes)}

    def search_teams(self, query):
        return self.teams.search(query.get("q", [""])[0], 100 if query.get("q", [""])[0].strip() else 40)

    def team_detail(self, team_id):
        record = self.teams.get_team(team_id)
        name_en, name_cn = self.resolver.get_team_names(team_id)
        roster = []
        for item in self.teams.roster(team_id):
            player = self.players.get_player(item["playerid"])
            position = player.get("preferredposition1")
            roster.append({
                **item,
                "overallrating": player.get("overallrating"),
                "primary_position": POSITION_NAMES.get(position, str(position)),
            })
        return {
            "teamid": team_id,
            "name": name_cn or name_en or str(team_id),
            "name_en": name_en,
            "name_cn": name_cn,
            "overallrating": record.get("overallrating"),
            "attackrating": record.get("attackrating"),
            "midfieldrating": record.get("midfieldrating"),
            "defenserating": record.get("defenserating"),
            "roster": roster,
        }

    def update_team_numbers(self, team_id, body):
        assignments = {int(key): int(value) for key, value in body.get("assignments", {}).items()}
        changes = self.rosters.renumber(team_id, assignments)
        self._record_changes(changes)
        self._log_changes(f"球队 {team_id} 球衣号码调整", changes)
        return {"applied": len(changes), "pending_changes": len(self.changes)}

    def transfer_player(self, body):
        try:
            player_id = int(body["player_id"])
            from_team_id = int(body["from_team_id"])
            to_team_id = int(body["to_team_id"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("转会请求必须包含有效的 player_id、from_team_id 和 to_team_id")
        changes = self.rosters.transfer_in_place(player_id, from_team_id, to_team_id)
        self.resolver.refresh_player_teams(self.rosters.table)
        self.players.resolver.refresh_player_teams(self.rosters.table)
        self.teams.resolver.refresh_player_teams(self.rosters.table)
        self._record_changes(changes)
        self._log_changes(f"球员 {player_id} 转会", changes)
        record = next(r for r in self.rosters.links(player_id) if r.get("teamid") == to_team_id)
        return {
            "playerid": player_id,
            "player_name": self.resolver.get_name_by_player_id(player_id),
            "from_team_id": from_team_id,
            "to_team_id": to_team_id,
            "jerseynumber": record.get("jerseynumber", 0),
            "applied": len(changes),
            "pending_changes": len(self.changes),
        }

    def team_options(self):
        return {"clubs": self.rosters.team_options(False), "national_teams": self.rosters.team_options(True)}

    def national_detail(self, team_id):
        service = NationalService(self.rosters)
        nation, links = service.context(team_id)
        candidates = []
        # 男足/女足共用 nationality id，按名单性别过滤；同时排除 5v5/Rush 占位球员
        gender = service.roster_gender(links)
        placeholders = service.placeholder_player_ids()
        unavailable = {
            record.get("playerid")
            for record in self.rosters.table.records
            if record.get("teamid") != team_id
            and self.resolver.is_national_team(record.get("teamid"))
        }
        for record, name, name_cn in self.player_index:
            if record.get("nationality") != nation:
                continue
            player_id = record["playerid"]
            if not service.is_candidate(record, gender, placeholders):
                continue
            club, _national = self.resolver.get_player_team(player_id)
            candidates.append({
                "playerid": player_id,
                "name": name,
                "name_cn": name_cn,
                "overallrating": record.get("overallrating", 0),
                "primary_position": POSITION_NAMES.get(
                    record.get("preferredposition1"), ""
                ),
                "position": record.get("preferredposition1"),
                "club": club or "",
                "unavailable": player_id in unavailable,
            })
        return {
            **self.team_detail(team_id),
            "nation_id": nation,
            "candidates": candidates,
            "gender": gender,
            "excluded_placeholders": len(placeholders),
            "roster_size": len(links),
            "expected_roster_size": service.expected_roster_size(links),
            "editable": len(links) >= service.MIN_ROSTER_SIZE,
        }

    def update_national(self, team_id, body):
        changes = NationalService(self.rosters).apply(team_id, body)
        for resolver in (
            self.resolver,
            self.players.resolver,
            self.teams.resolver,
            self.rosters.resolver,
        ):
            resolver.refresh_player_teams(self.rosters.table)
        self._record_changes(changes)
        self._log_changes(f"国家队 {team_id} 选拔", changes)
        return {"applied": len(changes), "pending_changes": len(self.changes)}

    def quick_legend_preview(self, body=None):
        body = body or {}
        include_women = as_bool(body.get("include_women"), False)
        include_all = as_bool(body.get("scope_all") or body.get("include_all"), False) \
            or str(body.get("scope", "")).lower() == "all"
        return LegendService(self.sav, include_women=include_women).preview(include_all=include_all)

    def quick_set_age18(self, age=18):
        changes = QuickFeatureService(self.sav).set_all_players_age(age)
        self._record_changes(changes)
        self._log(f"已将 {len(changes)} 名球员的年龄设置为 {age} 岁")
        return {
            "applied": len(changes),
            "players_updated": len(changes),
            "age": age,
            "pending_changes": len(self.changes),
        }

    def quick_birthdate_status(self):
        service = QuickFeatureService(self.sav)
        return {
            **service.preview_original_birthdays(),
            **service.birthdate_report(),
        }

    def quick_restore_birthdays(self):
        changes = QuickFeatureService(self.sav).restore_original_birthdays()
        self._record_changes(changes)
        self._log(f"已从生日快照恢复 {len(changes)} 名球员的原始生日")
        return {
            "applied": len(changes),
            "players_updated": len(changes),
            "pending_changes": len(self.changes),
        }

    def quick_peak_preview(self, body=None):
        body = body or {}
        service = PeakRestoreService(self.sav)
        return service.preview(
            min_peak=int(body.get("min_peak", 85)),
            min_age=int(body.get("min_age", 30)),
            include_clubless=as_bool(body.get("include_clubless"), True),
            skip_same_name=as_bool(body.get("skip_same_name"), True),
            include_done=as_bool(body.get("include_done") or body.get("scope_all"), False)
            or str(body.get("scope", "")).lower() == "all",
        )

    def quick_restore_peak(self, body=None):
        body = body or {}
        service = PeakRestoreService(self.sav)
        changes, result = service.apply(
            min_peak=int(body.get("min_peak", 85)),
            min_age=int(body.get("min_age", 30)),
            include_clubless=as_bool(body.get("include_clubless"), True),
            only_raise=as_bool(body.get("only_raise"), True),
            skip_same_name=as_bool(body.get("skip_same_name"), True),
        )
        if len(changes):
            self._record_changes(changes)
        self._log(
            f"已恢复 {result['restored_count']} 名现役老将的 FIFA19 巅峰"
            f"（{result['field_count']} 项属性）"
        )
        return {
            "applied": len(changes),
            "pending_changes": len(self.changes),
            **result,
        }

    def quick_add_legends(self, body=None):
        body = body or {}
        include_women = bool(body.get("include_women", False))
        service = LegendService(self.sav, include_women=include_women)
        changes, result = service.add_missing_legends()
        if len(changes):
            self._rebuild_indexes()
            self._record_changes(changes)
        self._log(
            f"已添加 {result['added']} 名当前存档缺失的传奇球员"
            f"（男足，含补充姓名 {result.get('names_added', 0)} 条）"
        )
        return {
            "added": result["added"],
            "legends": result["legends"],
            "names_added": result.get("names_added", 0),
            "women_skipped": result.get("women_skipped", 0),
            "include_women": include_women,
            "applied": len(changes),
            "pending_changes": len(self.changes),
        }

    def save(self):
        if not self.changes:
            raise ValueError("没有待保存的修改")
        result = SafeSaveService(self.meta).save(self.sav, self.changes.values())
        changed = len(self.changes)
        self.load(result.path)
        self._log(f"保存完成并重新加载验证：{result.path.name}")
        return {"path": str(result.path), "name": result.path.name, "verified_changes": changed}

    def reset(self):
        if not self.sav.filepath:
            raise ValueError("尚未加载存档")
        path = self.sav.filepath
        self.load(path)
        return self.summary()

    def _record_changes(self, changes):
        for change in changes:
            if isinstance(change, RecordChange):
                key = (change.table, change.key_field, change.key_value, "__record__")
                self.changes[key] = change
                continue
            if not isinstance(change, FieldChange):
                continue
            key = (change.table, change.key_field, change.key_value, change.field)
            previous = self.changes.get(key)
            old_value = previous.old_value if previous else change.old_value
            if change.new_value == old_value:
                self.changes.pop(key, None)
            else:
                self.changes[key] = FieldChange(change.table, change.key_field, change.key_value, change.field, old_value, change.new_value)


def create_app(state=None):
    state = state or EditorState()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.json.ensure_ascii = False

    @app.after_request
    def no_cache(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def value_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(404)
    def not_found(_exc):
        return jsonify(error="页面或接口不存在"), 404

    @app.route("/")
    def index():
        response = send_from_directory(WEB_ROOT, "index.html")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.route("/<path:name>")
    def static_file(name):
        if name not in ("app.js", "styles.css"):
            return jsonify(error="页面不存在"), 404
        return send_from_directory(WEB_ROOT, name)

    @app.route("/heads/p<int:player_id>.png")
    def player_head(player_id):
        return send_from_directory(HEADS_ROOT, f"p{player_id}.png")

    @app.route("/api/state")
    def api_state():
        with state.lock:
            return jsonify(state.summary())

    @app.route("/api/meta")
    def api_meta():
        with state.lock:
            return jsonify(positions=[{"value": value, "label": label} for value, label in sorted(POSITION_NAMES.items())], **state.team_options())

    @app.route("/api/players")
    def api_players():
        with state.lock:
            return jsonify(state.search_players(request.args.to_dict(flat=False)))

    @app.route("/api/players/<int:player_id>")
    def api_player(player_id):
        with state.lock:
            return jsonify(state.player_detail(player_id))

    @app.route("/api/teams")
    def api_teams():
        with state.lock:
            return jsonify(state.search_teams(request.args.to_dict(flat=False)))

    @app.route("/api/teams/<int:team_id>")
    def api_team(team_id):
        with state.lock:
            return jsonify(state.team_detail(team_id))

    def require_token():
        if request.headers.get("X-Editor-Token") != state.token:
            return jsonify(error="写入令牌无效"), 403
        return None

    @app.route("/api/players/<int:player_id>", methods=["POST"])
    def api_update_player(player_id):
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.update_player(player_id, request.get_json() or {}))

    @app.route("/api/players/<int:player_id>/traits", methods=["POST"])
    def api_update_trait(player_id):
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.update_trait(player_id, request.get_json() or {}))

    @app.route("/api/teams/<int:team_id>/numbers", methods=["POST"])
    def api_update_numbers(team_id):
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.update_team_numbers(team_id, request.get_json() or {}))

    @app.route("/api/transfers", methods=["POST"])
    def api_transfer():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.transfer_player(request.get_json() or {}))

    @app.route("/api/national-teams/<int:team_id>", methods=["GET", "POST"])
    def api_national(team_id):
        if request.method == "POST":
            denied = require_token()
            if denied:
                return denied
        with state.lock:
            if request.method == "POST":
                return jsonify(state.update_national(team_id, request.get_json() or {}))
            return jsonify(state.national_detail(team_id))

    @app.route("/api/quick/legends")
    def api_quick_legends():
        body = request.args.to_dict()
        with state.lock:
            return jsonify(state.quick_legend_preview(body))

    @app.route("/api/quick/age18", methods=["POST"])
    def api_quick_age18():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            age = (request.get_json() or {}).get("age", 18)
            try:
                age = int(age)
            except (TypeError, ValueError):
                age = 18
            return jsonify(state.quick_set_age18(age))

    @app.route("/api/quick/birthdates")
    def api_quick_birthdates():
        with state.lock:
            return jsonify(state.quick_birthdate_status())

    @app.route("/api/quick/restore-birthdays", methods=["POST"])
    def api_quick_restore_birthdays():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.quick_restore_birthdays())

    @app.route("/api/quick/peak", methods=["GET", "POST"])
    def api_quick_peak():
        body = request.get_json(silent=True) or request.args.to_dict() or {}
        if request.method == "POST":
            denied = require_token()
            if denied:
                return denied
            with state.lock:
                return jsonify(state.quick_restore_peak(body))
        with state.lock:
            return jsonify(state.quick_peak_preview(body))

    @app.route("/api/quick/add-legends", methods=["POST"])
    def api_quick_add_legends():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.quick_add_legends(request.get_json(silent=True) or {}))

    @app.route("/api/save", methods=["POST"])
    def api_save():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.save())

    @app.route("/api/reset", methods=["POST"])
    def api_reset():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            return jsonify(state.reset())

    @app.route("/api/pick-save", methods=["POST"])
    def api_pick_save():
        denied = require_token()
        if denied:
            return denied
        # 这里刻意不加 state.lock：系统对话框会一直阻塞到用户选择为止。
        try:
            return jsonify(state.pick_save_path())
        except Exception as exc:
            return jsonify({"error": str(exc), "cancelled": False})

    @app.route("/api/open", methods=["POST"])
    def api_open():
        denied = require_token()
        if denied:
            return denied
        body = request.get_json() or {}
        with state.lock:
            if body.get("filename"):
                state.load_by_filename(body["filename"])
            else:
                state.load(body.get("path", ""))
            return jsonify(state.summary())

    app.editor_state = state
    return app


def build_parser():
    parser = argparse.ArgumentParser(description="FC26 存档编辑器 Web 前端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--open", "--save", dest="startup_path", help="启动时打开指定存档")
    return parser


def main():
    from waitress import serve

    args = build_parser().parse_args()
    state = EditorState(args.startup_path)
    app = create_app(state)
    url = f"http://{args.host}:{args.port}/"
    print("========================================", flush=True)
    print("FC26 存档编辑器 Web 服务已启动", flush=True)
    print(f"服务地址：{url}", flush=True)
    if state.sav.filepath:
        print(f"当前存档：{state.sav.filepath.name}", flush=True)
    print("保存会生成新的 Squads 时间戳文件，原存档不会被覆盖。", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    serve(app, host=args.host, port=args.port, threads=6)


if __name__ == "__main__":
    main()
