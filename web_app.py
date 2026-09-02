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

from core.config import choose_startup_save, load as load_config, save as save_config
from core.mappings import ATTRIBUTE_CATEGORIES, NATIONS_CN, OPTION_MAPS, POSITION_NAMES
from core.meta_parser import MetaDatabase
from core.name_resolver import NameResolver
from core.sav_file import SavFile
from core.traits import FC26_TRAIT1, FC26_TRAIT2
from services.changes import ChangeSet, FieldChange
from services.player_service import PlayerService
from services.roster_service import RosterService
from services.save_service import SafeSaveService
from services.team_service import TeamService


APP_ROOT = Path(__file__).resolve().parent
WEB_ROOT = APP_ROOT / "web"
HEADS_ROOT = APP_ROOT / "data" / "heads"
META_PATH = APP_ROOT / "data" / "fifa_ng_db-meta.xml"


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

    def load(self, path):
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"找不到存档：{path}")
        sav = SavFile()
        sav.load(path, self.meta)
        self.sav = sav
        self.changes.clear()
        self.resolver = NameResolver(sav.db)
        self.players = PlayerService(sav)
        self.rosters = RosterService(sav)
        self.teams = TeamService(sav)
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

    def _log(self, message):
        if self.remember_path:
            print(f"[操作] {message}", flush=True)

    def _log_changes(self, label, changes):
        details = []
        for change in changes:
            if isinstance(change, FieldChange):
                details.append(f"{change.table}.{change.field} {change.old_value}->{change.new_value}")
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

    @app.route("/api/open", methods=["POST"])
    def api_open():
        denied = require_token()
        if denied:
            return denied
        with state.lock:
            state.load((request.get_json() or {}).get("path", ""))
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
