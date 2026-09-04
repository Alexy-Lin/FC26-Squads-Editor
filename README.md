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
- 快捷功能：一键添加当前存档缺失的传奇球员 / Quick feature: add missing legends in one click
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

启动时会自动加载 FC26 存档目录中修改时间最新的 `Squads*` 文件。也可以点击“打开存档”并输入存档完整路径。

At startup, the editor automatically loads the newest `Squads*` file in the FC26 save folder. You can also click “打开存档” and enter a full save path.

基本操作 / Basic workflow:

1. 在“球员编辑”中搜索并选择球员。 / Search for and select a player in “球员编辑”.
2. 修改字段，或选择球队、国家队和特性。 / Edit fields or select a club, national team, or trait.
3. 点击“应用球员修改”。修改暂时只保存在内存中。 / Click “应用球员修改”. Changes remain in memory temporarily.
4. 确认无误后点击“保存为新存档”。 / Click “保存为新存档” after reviewing the changes.

球队页面可以查看阵容并批量填写球衣号码。转会页面可以选择来源球队和目标球队，再点击球员对应的转会按钮。

“国家队选拔”页面可以选择国家队，按姓名、能力和位置筛选同国籍球员，移入或移出候选人并编辑号码。名单必须满足 FC26 的 26 人规则，点击“应用选拔与号码”后，再点击顶部“保存为新存档”。

“快捷功能”页面提供两个一键操作：

1. “设置全部球员为 18 岁”：把当前存档所有球员的年龄统一设置为 18 岁。
2. “一键添加缺失传奇”：读取项目内置传奇清单，把当前存档中没有的传奇球员以自由球员身份加入。

两个操作都会先暂存修改，不会覆盖原存档；完成后请点击顶部“保存为新存档”。再次点击“放弃修改”即可撤销尚未保存的操作。

The Teams page supports squad viewing and batch shirt-number editing. The Transfers page lets you select a source and target club, then transfer players individually.

The National Team page lets you choose a country, filter eligible players by name, rating, or position, add or remove players, and edit shirt numbers. The roster must contain 26 players for FC26. Apply the selection first, then click “Save as new save”.

The “Quick Features” page provides two one-click actions:

1. “Set all players to age 18” updates the age of every player in the loaded save.
2. “Add missing legends” adds legends from the bundled list that are not already in the save, as free agents.

Both actions are staged in memory first. Click “Save as new save” when ready; click “Discard changes” to undo anything that has not been saved.

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

在“打开存档”中输入完整路径。FC26 默认存档目录通常是：

Enter the full path in “打开存档”. The default FC26 save folder is usually:

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
