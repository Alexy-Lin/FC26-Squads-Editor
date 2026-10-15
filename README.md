# FC26 存档编辑器 / FC26 Squads Editor

EA SPORTS FC 26 `Squads` save editor with a Chinese Web interface, command-line tools, and Excel export.

EA SPORTS FC 26 `Squads` 存档编辑器，提供中文 Web 界面、命令行工具和 Excel 导出功能。

## 功能 / Features

- 搜索球员：姓名、中文名或球员 ID / Search players by name, Chinese name, or player ID
- 按国籍、位置和总评筛选 / Filter by nationality, position, and overall rating
- 球员详情页优先显示内置头像，未匹配时显示姓名首字母 / Show bundled player heads when available, with an initial fallback
- 修改总评、潜力、能力值、位置、角色、惯用脚、逆足、花式和身体数据 / Edit ratings, potential, attributes, positions, roles, feet, skill moves, and physical data
- 修改普通特性和图标特性 / Edit regular and icon traits
- 查看球队阵容并批量修改球衣号码 / View squads and batch-edit shirt numbers
- 俱乐部、自由球员之间转会 / Transfer players between clubs and free agents
- 国家队选拔：按国籍筛选候选人，选出 26 人并设置号码 / Select 26-player national squads by nationality and assign shirt numbers
- 快捷功能：批量设置全部球员为 18 岁 / Quick feature: set all players to age 18
- 快捷功能：一键恢复原始生日（自动快照）/ Quick feature: restore original birthdays from an automatic snapshot
- 快捷功能：一键添加当前存档缺失的男足传奇球员（含 Kempes / Rivellino，使用真实生日，自动跳过女足）/ Quick feature: add missing **male** legends, including Kempes and Rivellino, with real birthdates
- 快捷功能：一键现役传奇恢复巅峰（41 项属性含门将，FIFA19 两套数据取高，只升不降）/ Quick feature: restore active veterans to their FIFA19 peak (41 attributes including goalkeeping, best of two FIFA19 sources, raise-only)
- 导出球员表或完整存档数据到 Excel / Export player tables or complete save data to Excel

## 安装 / Installation

### 要求 / Requirements

- Windows 10/11
- Python 3.10 或更高版本 / Python 3.10 or newer
- FC26 本地 `Squads` 存档 / A local FC26 `Squads` save

### 自动安装 / Automatic setup

在项目根目录双击 `start_editor.bat`。脚本会自动选择 Python，并安装缺少的依赖。

Double-click `start_editor.bat` in the project folder. It automatically selects Python and installs missing dependencies.

### 手动安装 / Manual setup

在项目目录打开 PowerShell，执行：

Open PowerShell in the project folder and run:

```powershell
python -m pip install -r requirements.txt
```

## Web 界面 / Web interface

启动服务 / Start the service:

```powershell
python web_app.py
```

然后打开 / Then open:

```text
http://127.0.0.1:8765/
```

启动时会自动加载 FC26 存档目录中修改时间最新的 `Squads*` 文件。点击“打开存档”会直接弹出**系统文件选择窗口**（Windows 资源管理器对话框，默认打开 FC26 存档目录），选好文件立即加载，不需要手填路径；用户取消则不做任何事。
如果系统窗口无法弹出（例如服务跑在没有桌面的环境），会自动退回到备用弹窗，里面可以：在浏览器文件管理器里选文件（按文件名在 FC26 存档目录里查找）、重试系统窗口、或手动输入完整路径。

At startup, the editor automatically loads the newest `Squads*` file in the FC26 save folder. Clicking “打开存档” opens the **native Windows file dialog** (starting in the FC26 save folder); the chosen save is loaded immediately and no path has to be typed. Cancelling does nothing. If the native dialog cannot be shown (headless server), a fallback dialog offers: picking a file in the browser's file manager (resolved by name inside the FC26 save folder), retrying the native dialog, or typing a full path.

基本操作 / Basic workflow:

1. 在“球员编辑”中搜索并选择球员。 / Search for and select a player in “球员编辑”.
2. 修改字段，或选择球队、国家队和特性。 / Edit fields or select a club, national team, or trait.
3. 点击“应用球员修改”。修改暂时只保存在内存中。 / Click “应用球员修改”. Changes remain in memory temporarily.
4. 确认无误后点击“保存为新存档”。 / Click “保存为新存档” after reviewing the changes.

球队页面可以查看阵容并批量填写球衣号码。转会页面可以选择来源球队和目标球队，再点击球员对应的转会按钮。

“国家队选拔”页面可以选择国家队，按姓名、能力和位置筛选同国籍球员，移入或移出候选人并编辑号码。名单必须满足 FC26 的 26 人规则，点击“应用选拔与号码”后，再点击顶部“保存为新存档”。

候选名单的过滤规则（针对真实存档踩过的坑）：

- **国家队列表由存档自动识别**：`core/name_resolver.py` 除了原来的固定 id 表，还会用存档自带的 `CxJp`（team→nation）+ 队名等于国家名 + 名单国籍一致来识别国家队。这样 FC26 新增的球队（日本、韩国、摩洛哥、乌克兰、克罗地亚、沙特、伊朗、阿尔及利亚、乌兹别克斯坦、卡塔尔、印尼、伊拉克、约旦、巴拿马、海地、佛得角、加纳、塞内加尔、突尼斯…）以及**女足国家队**（113xxx/115xxx）都能选，而且它们不再被当成"俱乐部"出现在转会页；`那不勒斯`、`阿森纳` 这类 26 人俱乐部不会被误判（名单国籍测试会挡掉）。
- **按名单性别过滤**：FC26 里男足和女足共用同一个 `nationality` id，只按国籍筛选会把女足球员（例如英格兰的 Alessia Russo / Lucy Bronze / Leah Williamson）塞进男足候选。现在由现有名单的性别决定候选池：英格兰男足(1318) 只给男足，英格兰女足(113002) 只给女足。
- **排除小场模式与经理池记录**：`Rush Goalkeeper`（只挂在 `5 对 5 球队`）和**经理记录**（例如第二个 `Zinedine Zidane`，id 238399，只挂在 `自由球员经理` 池里 —— 选法国队时会看到两个齐达内，现在只剩 ICON 版 1397）都不会再出现在候补名单里；判据集中在 `NameResolver.is_non_player_team()`（`5 对 5 / 5v5 / Rush / 经理 / manager` 等标记），这些占位球队也从转会页的球队列表里去掉（自由球员池不受影响）。
- **男足 / 女足切换**：国家队选择框旁边有「男足 / 女足」按钮，**默认男足**；女足队的名字都会带 `· 女足` 标记（例如 `德国 · 女足 (ID=113004)`），所以即使不切换也不会认错。该字段同样出现在转会页的球队列表里（女足俱乐部也会带标记）。
- **经典号码自动编号**：名单下方有「按位置自动编号（经典号码）」，主力按位置拿固定号码：

  | 号码 | 位置 | 挑谁 |
  |---|---|---|
  | 1 | 门将 | 能力最高的门将 |
  | 2 / 3 | 右后卫 / 左后卫 | 该位置能力最高者 |
  | 4 / 5 | 中卫 | 能力最高的两名中卫 |
  | 6 | 后腰 CDM | 能力最高者 |
  | 8 | 中前卫 CM | 能力最高者 |
  | 10 | 前腰 CAM | 能力最高者 |
  | 7 / 11 | 右路 / 左路 | 该位置能力最高者 |
  | 9 | 中锋 ST | 能力最高的中锋 |

  优先按位置匹配（RB→2、LB→3、CB→4/5、CDM→6、CM→8、CAM→10、RW→7、LW→11、ST→9），该位置没人就退化为该组能力最高者；**替补**按 门将 → 后卫 → 中场 → 前锋、组内能力从高到低，从 12 开始拿剩下的号码（满编 26 人时替补门将通常拿 12）。另有「按当前排序编号」沿用按表格排序顺序编号的老方式。
- 接口会在返回里附带 `gender`、`expected_roster_size` 与 `excluded_placeholders` 便于核对；候选球员带 `position`（FC26 位置 id）与 `overallrating`，自动编号在前端本地完成，不额外发请求。
- **原位选拔按该队原有人数**：男足 26 人，女足 23 人；编辑器重写的是已有的 `RrqT` 记录，人数保持不变，所以不会因为 23 人名单而拒绝编辑。

The National Team page lets you choose a country, filter eligible players by name, rating, or position, add or remove players, and edit shirt numbers. The roster must contain 26 players for FC26. Apply the selection first, then click “Save as new save”.

Candidate filtering (all are real-save findings):

- **The national-team list is detected from the save**: besides the fixed id table, `core/name_resolver.py` recognises a team as national when the save links it to a nation (`CxJp`), its name equals a nation name and its roster is dominated by that nation. That brings in FC26's newer teams (Japan, Korea, Morocco, Ukraine, Croatia, Saudi Arabia, Iran, Algeria, Uzbekistan, Qatar, Indonesia, Iraq, Jordan, Panama, Haiti, Cape Verde, Ghana, Senegal, Tunisia, ...) and the **women's national teams** (113xxx/115xxx), and removes them from the transfer page's club list. 26-man clubs such as Napoli or Arsenal are not misclassified.
- **Filtered by roster gender**: men's and women's players share the same `nationality` id in FC26, so a nationality-only filter offered women (England's Alessia Russo / Lucy Bronze / Leah Williamson) for the men's team. The existing roster's gender now decides the pool: England men (1318) offers men, England women (113002) offers women.
- **Small-sided placeholders excluded**: ``Rush Goalkeeper`` style 5v5/Rush placeholders live only on the `5 对 5 球队` teams and no longer show up as candidates (detected by every club link pointing at a small-sided team).
- **Men's / women's toggle**: the national-team picker has a “男足 / 女足” (men / women) switch, **men by default**; women's teams always carry a `· 女足` marker in their label (e.g. `德国 · 女足 (ID=113004)`), and the same gender field is exposed for clubs on the transfers page.
- **In-place selection keeps the team's own size**: 26 for men's teams, 23 for the women's teams; the editor rewrites the existing `RrqT` links, so the count never changes.

“快捷功能”页面提供四个一键操作，其中传奇和现役老将两张卡片各带一个 **“查看名单”** 按钮，点击弹出完整名单弹窗：

| 弹窗 | 内容 |
|---|---|
| 传奇球员名单（男足） | 共识别 N 名 / 已有 / 待添加；每行显示 ID、姓名、状态（将添加·已有）、OVR、生日、生日来源、清单来源（官方清单 / 额外补充 Kempes·Rivellino）。数据来自 `GET /api/quick/legends?scope=all`。 |
| 现役老将名单（FIFA19 巅峰） | 共 N 名（口径：年龄 ≥ 30、FIFA19 巅峰 OVR ≥ 85）；每行显示 ID、姓名、年龄、现在 OVR、巅峰 OVR、OVR 提升、**需补项数**、状态（待恢复·已达标）、位置（门将/外场）、俱乐部。待恢复的排在前面。数据来自 `GET /api/quick/peak?include_done=1`。 |

1. “设置全部球员为 18 岁”：把当前存档所有球员的年龄统一设置为 18 岁。执行前会自动把原始生日写入 `data/birthdate_snapshots/`（每个存档一份 + `latest.json`）。
2. “一键恢复原始生日”：用上面的生日快照把所有球员（含传奇）还原成真实生日。没有快照时按钮置灰，并提示先执行一次 18 岁或手动重新打开原始存档。
3. “一键添加缺失传奇”：读取项目内置传奇清单，把当前存档中没有的**男足**传奇以自由球员身份加入，**女足 ICON/英雄会被自动跳过**（按源数据库 `gender` 字段判断，当前清单里 183 男 / 23 女）。包含清单外的 **Kempes（82092）** 和 **Rivellino（191190）**；所有导入球员都写入**真实生日**（来源库里的占位生日 120000/130000 会被游戏隐藏，导致球员在国家队选拔里看不到），需要时补写 `editedplayernames` 姓名。需要连女足一起补时调用 `POST /api/quick/add-legends {"include_women": true}`。
4. “一键现役传奇恢复巅峰”：把 30 岁以上的现役老将（梅西、C 罗、内马尔、莫德里奇、莱万等）恢复到 FIFA19 巅峰。默认口径：巅峰 OVR ≥ 85、年龄 ≥ 30、包含没有俱乐部的现役球员、**只升不降**，自动排除传奇/ICON 与同名球员。
   - 比对 **41 项属性**：除总评/潜力外，还有 29 项外场、`aggression`、`defensiveawareness`，以及门将 5 项（`gkdiving`/`gkhandling`/`gkkicking`/`gkpositioning`/`gkreflexes`，只写给门将）。门将属性来自官方 FIFA19 导出，只补门将。
   - 巅峰参考值取**两套 FIFA19 数据的较高者**：`players.db` 的 `fifa19` 行 + 官方 sofifa FIFA19 导出（`players_19.csv`）。两者会不一致（例如德佩：存档值加速 82，官方值 89），只取存档那一套会漏掉单项。
   - OVR 已经等于巅峰、但仍有单项属性偏低的球员同样会恢复（德佩就是这种：86 = 巅峰 86，但加速/速度/任意球/侵略性等 7 项偏低）。
   - 数据由 `tools/export_fifa19_peak.py` 生成到 `data/fifa19_peak.csv`（41 列，5856 行），该 CSV 已随仓库提供，克隆后即可直接使用。需要重新生成时才运行上述脚本（生成用的 `players.db` 与官方 `players_19.csv` 不随仓库提供）。

四个操作都会先暂存修改，不会覆盖原存档；完成后请点击顶部“保存为新存档”。再次点击“放弃修改”即可撤销尚未保存的操作。

The Teams page supports squad viewing and batch shirt-number editing. The Transfers page lets you select a source and target club, then transfer players individually.

The National Team page lets you choose a country, filter eligible players by name, rating, or position, add or remove players, and edit shirt numbers. The roster must contain 26 players for FC26. Apply the selection first, then click “Save as new save”.

The “Quick Features” page provides four one-click actions; the legend card and the veteran card each have a **“查看名单” (View list)** button that opens a modal with the full list:

| Dialog | Contents |
|---|---|
| Legend players (male) | recognised / already present / to be added counts, then one row per legend: ID, name, status, OVR, birthdate, birthdate source, list origin (official list / extra: Kempes, Rivellino). `GET /api/quick/legends?scope=all` |
| Active veterans (FIFA19 peak) | players aged 30+ with a FIFA19 peak of 85+: ID, name, age, current OVR, peak OVR, OVR gain, attributes still to raise, status (to restore / already at peak), position (GK/outfield), club. Pending rows come first. `GET /api/quick/peak?include_done=1` |

1. “Set all players to age 18” — also writes an automatic birthdate snapshot to `data/birthdate_snapshots/`.
2. “Restore original birthdays” — restores every player (legends included) from that snapshot.
3. “Add missing **male** legends” — women's ICONs/Heroes are skipped automatically (detected through the source `gender` field: 183 male / 23 female in the current list). It includes **Kempes (82092)** and **Rivellino (191190)** even though they are not in the icon list, and imports every legend with its **real birthdate** (the source placeholders 120000/130000 are rejected by the game and hide the player) plus an `editedplayernames` record when needed. Pass `{"include_women": true}` to `POST /api/quick/add-legends` to include the women.
4. “Restore active veterans to peak” — 41 attributes per player (29 outfield + `aggression` + `defensiveawareness` + the 5 goalkeeper attributes, goalkeeper ones only written to goalkeepers), raise-only, active players aged 30+ with a FIFA19 peak of 85+. The peak reference is the **higher of the two FIFA19 sources** (`players.db`'s `fifa19` rows and the official sofifa FIFA19 export), and players whose OVR already matches the peak but still have low individual attributes are restored as well (Memphis Depay: 86 = peak 86, seven attributes below peak). Legends and same-name players are excluded. The reference table ships with the repository as `data/fifa19_peak.csv` (41 columns, 5,856 rows), so it works right after cloning. Re-generate it with `tools/export_fifa19_peak.py` if needed (the `players.db` and official `players_19.csv` used to build it are not part of the repository).

All four actions are staged in memory first. Click “Save as new save” when ready; click “Discard changes” to undo anything that has not been saved.

## 命令行 / Command line

以下命令都在项目目录执行。请将示例路径替换为自己的 `Squads` 文件路径。

Run these commands from the project folder. Replace the example path with your own `Squads` save path.

```powershell
# 查看存档摘要 / Show save summary
python main.py C:\path\to\Squads20260902010101

# 搜索球员 / Search players
python main.py C:\path\to\Squads... --search Messi

# 查看球员资料 / Show player details
python main.py C:\path\to\Squads... --player 158023

# 预览修改，不写入文件 / Preview changes without writing a file
python main.py C:\path\to\Squads... --set 158023 overallrating=99 finishing=99

# 修改并生成新的时间戳存档 / Apply changes and create a timestamped save
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save

# 修改并保存到指定的新文件 / Save to a new output file
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save-as boosted.sav

# 修改球员的球队和球衣号码 / Change a player's club and shirt number
python main.py C:\path\to\Squads... --set-team 158023 47 10 --save

# 修改特性：player_id bank bit on|off / Edit a trait bit
python main.py C:\path\to\Squads... --set-trait 158023 1 6 on --save

# 导出 Excel / Export to Excel
python main.py C:\path\to\Squads... --export squad.xlsx
python main.py C:\path\to\Squads... --export-players players.xlsx
```

常用字段 / Common fields:

```text
overallrating, potential, finishing, dribbling, sprintspeed,
shotpower, ballcontrol, acceleration, agility, stamina, strength,
crossing, shortpassing, longpassing, volleys, composure,
preferredposition1, preferredfoot, weakfootabilitytypecode, skillmoves
```

字段也可以使用 FC26 的短名，例如 `BAPc=4`、`aOBn=5`。数值超出范围时会自动限制到有效范围；相对修改可以写成 `overallrating=+5`。

Fields may also use FC26 short names, such as `BAPc=4` or `aOBn=5`. Values outside the valid range are clamped automatically; use `overallrating=+5` for a relative change.

查看全部参数 / Show all options:

```powershell
python main.py --help
```

## 保存和备份 / Saving and backups

- Web 界面和 CLI 的 `--save` 会在原存档目录生成新的 `SquadsYYYYMMDDHHMMSS` 文件。 / The Web interface and CLI `--save` create a new `SquadsYYYYMMDDHHMMSS` file in the original save folder.
- `--save-as` 必须指定新的输出路径，程序不会覆盖已有文件。 / `--save-as` requires a new output path and will not overwrite an existing file.
- 原始存档不会被编辑器覆盖，仍建议先自行备份。 / The original save is not overwritten, but making a backup first is recommended.
- 保存完成后程序会自动重新读取并验证修改结果。 / The editor reloads and validates the result after saving.

## 常见问题 / Troubleshooting

### 找不到存档 / Save not found

点击“打开存档”后，系统文件选择窗口会默认停在 FC26 存档目录；如果列表是空的，先确认游戏里保存过阵容。FC26 默认存档目录通常是：

Clicking “打开存档” opens the system file dialog directly in the FC26 save folder. If it looks empty, make sure the game has saved a squad file. The default FC26 save folder is usually:

```text
C:\Users\你的用户名\AppData\Local\EA SPORTS FC 26\settings\
```

文件名一般类似 `Squads20260902010101`。 / A typical filename looks like `Squads20260902010101`.

### 依赖安装失败 / Dependency installation failed

确认已安装 Python，并在项目目录执行：

Make sure Python is installed, then run this from the project folder:

```powershell
python -m pip install -r requirements.txt
```

### 浏览器打不开 / Browser cannot connect

确认启动窗口仍在运行，然后手动访问 `http://127.0.0.1:8765/`。关闭命令窗口会停止编辑器服务。

Keep the startup window open and visit `http://127.0.0.1:8765/` manually. Closing the command window stops the editor service.

## 测试 / Tests

```powershell
python -m unittest discover -s tests -v
```

## 许可证 / License

本项目的原创源代码和文档采用 [Apache License 2.0](LICENSE) 授权。

The original source code and documentation in this project are licensed under the [Apache License 2.0](LICENSE).

仓库中随附的游戏衍生数据、数据库结构文件、球员姓名和头像等资源可能受 EA 或其他权利人的版权及使用条款约束；Apache License 2.0 不转让这些第三方权利。

Bundled game-derived data, database schema files, player names, player head images, and other third-party materials may be subject to the copyrights and terms of their respective owners. Apache License 2.0 does not transfer those third-party rights.
