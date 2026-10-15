# FC26 存档编辑器

EA SPORTS FC 26 `Squads` 存档编辑器。中文 Web 界面，支持球员修改、球队与转会管理、国家队选拔、传奇球员补充、现役老将巅峰恢复和 Excel 导出。

---

## 功能

### 球员编辑

- 按姓名、中文名或球员 ID 搜索球员
- 按国籍、位置、总评筛选
- 优先显示内置头像，未匹配时显示姓名首字母
- 修改总评、潜力、各项能力值、位置、角色、惯用脚、逆足、花式
- 修改身体数据（身高、体重等）
- 修改普通特性与图标特性

### 球队与转会

- 查看球队阵容，批量修改球衣号码
- 在俱乐部与自由球员之间转入、转出球员
- 球队列表自动标注男足 / 女足

### 国家队选拔

- 从存档自动识别全部国家队，包含 FC26 新增球队与女足国家队
- 男足 / 女足一键切换，默认男足
- 按姓名、能力、位置筛选同国籍候选人
- **按位置自动编号（经典号码）**：主力按位置拿固定号码（1 门将、2/3 边后卫、4/5 中卫、6 后腰、8 中前卫、10 前腰、7/11 边路、9 中锋），替补从 12 开始
- 按当前排序编号（沿用表格排序顺序）
- 名单人数遵循该队原有规模：男足 26 人，女足 23 人

### 快捷功能

| 功能 | 说明 |
|---|---|
| 设置全部球员为 18 岁 | 把当前存档所有球员年龄统一改为 18 岁，执行前自动保存生日快照 |
| 一键恢复原始生日 | 用生日快照把所有球员（含传奇）还原成真实生日 |
| 一键添加缺失传奇 | 把存档中还没有的男足传奇以自由球员身份加入，跳过女足 ICON / 英雄 |
| 一键现役老将恢复巅峰 | 把 30 岁以上现役老将恢复到 FIFA19 巅峰水平 |

传奇与现役老将两张卡片各带一个「查看名单」按钮，点击可查看完整名单、当前状态、能力变化等明细。

**现役老将恢复巅峰**的默认口径：

- 年龄 ≥ 30 岁，FIFA19 巅峰总评 ≥ 85
- 只升不降，不会削弱任何球员
- 自动排除传奇 / ICON 与同名球员
- 对比 41 项属性，包含门将 5 项（只写给门将）
- 总评已达巅峰但个别属性偏低的球员同样会恢复

### 导出

- 导出球员表到 Excel
- 导出完整存档数据到 Excel

---

## 安装

推荐让 AI 编程工具自动完成安装，无需手动克隆或配置环境。

把**仓库链接**和下面这段话一起发给 **opencode**、**workbuddy**、**Claude Code**、**Cursor** 等任意 AI 编程工具：

> 请帮我安装并运行这个项目：https://github.com/Alexy-Lin/FC26-Squads-Editor
>
> 把仓库克隆到本地，检查 Python 版本，安装 `requirements.txt` 里的依赖，然后启动编辑器并告诉我访问地址。

AI 工具会自行克隆仓库、阅读项目文件、安装依赖并启动服务。

### 手动安装

如果你想自己操作，先克隆仓库，再在项目目录双击 `start_editor.bat`。脚本会自动选择 Python、安装缺少的依赖并启动编辑器。

```powershell
git clone https://github.com/Alexy-Lin/FC26-Squads-Editor.git
```

也可以在项目目录打开 PowerShell 手动执行：

```powershell
python -m pip install -r requirements.txt
python web_app.py
```

### 环境要求

- Windows 10 / 11
- Python 3.10 或更高版本
- 本地存在 FC26 `Squads` 存档

---

## 使用

启动后浏览器会自动打开。如果没有自动打开，手动访问：

```text
http://127.0.0.1:8765/
```

关闭启动窗口即可停止编辑器。

### 打开存档

启动时会自动加载 FC26 存档目录中修改时间最新的 `Squads*` 文件。

点击「打开存档」会直接弹出系统文件选择窗口，默认停在 FC26 存档目录，选好文件立即加载，不需要手填路径；取消则不做任何事。

如果系统窗口无法弹出（例如服务运行在没有桌面的环境），会自动退回备用弹窗，可以选择在浏览器中挑文件、重试系统窗口，或手动输入完整路径。

FC26 默认存档目录通常是：

```text
C:\Users\你的用户名\AppData\Local\EA SPORTS FC 26\settings\
```

文件名一般类似 `Squads20260902010101`。

### 基本流程

1. 在「球员编辑」中搜索并选择球员
2. 修改字段，或选择球队、国家队和特性
3. 点击「应用球员修改」，修改暂时只保存在内存中
4. 确认无误后点击顶部「保存为新存档」

点击「放弃修改」可以撤销尚未保存的操作。

---

## 保存与备份

- 保存会在原存档目录生成新的 `SquadsYYYYMMDDHHMMSS` 文件，不会覆盖原存档
- 保存后程序会自动重新读取并验证修改结果
- 原始存档不会被编辑器覆盖，仍建议自行备份

---

## 命令行

以下命令都在项目目录执行，请把示例路径替换为自己的 `Squads` 文件路径。

```powershell
# 查看存档摘要
python main.py C:\path\to\Squads20260902010101

# 搜索球员
python main.py C:\path\to\Squads... --search Messi

# 查看球员资料
python main.py C:\path\to\Squads... --player 158023

# 预览修改，不写入文件
python main.py C:\path\to\Squads... --set 158023 overallrating=99 finishing=99

# 修改并生成新的时间戳存档
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save

# 修改并保存到指定的新文件
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save-as boosted.sav

# 修改球员的球队和球衣号码
python main.py C:\path\to\Squads... --set-team 158023 47 10 --save

# 修改特性：player_id bank bit on|off
python main.py C:\path\to\Squads... --set-trait 158023 1 6 on --save

# 导出 Excel
python main.py C:\path\to\Squads... --export squad.xlsx
python main.py C:\path\to\Squads... --export-players players.xlsx
```

常用字段：

```text
overallrating, potential, finishing, dribbling, sprintspeed,
shotpower, ballcontrol, acceleration, agility, stamina, strength,
crossing, shortpassing, longpassing, volleys, composure,
preferredposition1, preferredfoot, weakfootabilitytypecode, skillmoves
```

字段也可以使用 FC26 的短名，例如 `BAPc=4`、`aOBn=5`。数值超出范围会自动限制到有效范围；相对修改可以写成 `overallrating=+5`。

查看全部参数：

```powershell
python main.py --help
```

---

## 常见问题

### 找不到存档

点击「打开存档」后，系统文件选择窗口会默认停在 FC26 存档目录。如果列表是空的，请先确认游戏里保存过阵容。默认目录见上方「打开存档」。

### 依赖安装失败

确认已安装 Python，然后在项目目录执行：

```powershell
python -m pip install -r requirements.txt
```

### 浏览器打不开

确认启动窗口仍在运行，然后手动访问 `http://127.0.0.1:8765/`。关闭命令窗口会停止编辑器服务。

### 恢复巅峰功能提示缺少数据

`data/fifa19_peak.csv` 已随仓库提供，正常情况不会出现该提示。如果文件缺失，可以用 `python tools/export_fifa19_peak.py` 重新生成，该脚本需要额外的 FIFA19 数据源。

---

## 许可证

本项目的原创源代码和文档采用 [Apache License 2.0](LICENSE) 授权。

仓库中随附的游戏衍生数据、数据库结构文件、球员姓名和头像等资源可能受 EA 或其他权利人的版权及使用条款约束；Apache License 2.0 不转让这些第三方权利。

---
---

# FC26 Squads Editor

An EA SPORTS FC 26 `Squads` save editor with a Chinese web interface. Edit players, manage squads and transfers, select national teams, add legends, restore active veterans to their peak, and export to Excel.

---

## Features

### Player editing

- Search players by name, Chinese name, or player ID
- Filter by nationality, position, and overall rating
- Show bundled player heads when available, with an initial fallback
- Edit overall rating, potential, attributes, positions, roles, preferred foot, weak foot, and skill moves
- Edit physical data (height, weight, and more)
- Edit regular and icon traits

### Squads and transfers

- View squads and batch-edit shirt numbers
- Transfer players between clubs and free agents
- Club lists are labelled by men's / women's team

### National team selection

- Detects every national team from the save, including FC26's newer teams and women's national teams
- One-click men's / women's switch, men by default
- Filter eligible players by name, rating, or position
- **Automatic classic shirt numbering**: starters take position-based numbers (1 goalkeeper, 2/3 full-backs, 4/5 centre-backs, 6 defensive midfield, 8 central midfield, 10 attacking midfield, 7/11 wings, 9 striker), substitutes start from 12
- Number by current sort order instead, if you prefer
- Roster size follows the team's own size: 26 for men, 23 for women

### Quick features

| Feature | Description |
|---|---|
| Set all players to age 18 | Sets every player's age to 18, saving a birthdate snapshot first |
| Restore original birthdays | Restores every player, legends included, from that snapshot |
| Add missing legends | Adds missing **male** legends as free agents, skipping women's ICONs and Heroes |
| Restore veterans to peak | Restores active players aged 30+ to their FIFA19 peak |

Both the legend and the veteran cards have a **View list** button showing the full list, current status, and rating changes.

**Restore veterans to peak** uses these defaults:

- Age 30 or above, FIFA19 peak overall of 85 or higher
- Raise only, so no player is ever weakened
- Legends, ICONs, and same-name players are excluded
- Compares 41 attributes, including 5 goalkeeper attributes written only to goalkeepers
- Players already at their peak overall but low on individual attributes are restored too

### Export

- Export player tables to Excel
- Export complete save data to Excel

---

## Installation

The recommended way is to let an AI coding tool handle the setup, so there is nothing to clone or configure by hand.

Send the **repository link** together with the prompt below to **opencode**, **workbuddy**, **Claude Code**, **Cursor**, or any similar AI coding tool:

> Please install and run this project for me: https://github.com/Alexy-Lin/FC26-Squads-Editor
>
> Clone the repository locally, check the Python version, install the dependencies from `requirements.txt`, then start the editor and tell me the address to open.

The tool will clone the repository, read the project files, install dependencies, and start the service on its own.

### Manual installation

To do it yourself, clone the repository first, then double-click `start_editor.bat` in the project folder. It selects Python automatically, installs any missing dependencies, and starts the editor.

```powershell
git clone https://github.com/Alexy-Lin/FC26-Squads-Editor.git
```

You can also open PowerShell in the project folder and run:

```powershell
python -m pip install -r requirements.txt
python web_app.py
```

### Requirements

- Windows 10 / 11
- Python 3.10 or newer
- A local FC26 `Squads` save

---

## Usage

The browser opens automatically after startup. If it does not, open this address manually:

```text
http://127.0.0.1:8765/
```

Close the startup window to stop the editor.

### Opening a save

At startup the editor automatically loads the newest `Squads*` file in the FC26 save folder.

Clicking **Open save** opens the native Windows file dialog directly in the FC26 save folder. The chosen save is loaded immediately and no path has to be typed; cancelling does nothing.

If the native dialog cannot be shown (for example on a headless server), a fallback dialog lets you pick a file in the browser, retry the native dialog, or type a full path.

The default FC26 save folder is usually:

```text
C:\Users\YOUR_NAME\AppData\Local\EA SPORTS FC 26\settings\
```

A typical filename looks like `Squads20260902010101`.

### Basic workflow

1. Search for and select a player in **Player editor**
2. Edit fields, or choose a club, national team, or trait
3. Click **Apply player changes**; changes are held in memory for now
4. Click **Save as new save** at the top once you are happy with them

Click **Discard changes** to undo anything that has not been saved.

---

## Saving and backups

- Saving creates a new `SquadsYYYYMMDDHHMMSS` file in the original save folder; the original is never overwritten
- The editor reloads and validates the result after saving
- The original save is never overwritten, but making a backup first is still recommended

---

## Command line

Run these commands from the project folder, replacing the example path with your own `Squads` save path.

```powershell
# Show save summary
python main.py C:\path\to\Squads20260902010101

# Search players
python main.py C:\path\to\Squads... --search Messi

# Show player details
python main.py C:\path\to\Squads... --player 158023

# Preview changes without writing a file
python main.py C:\path\to\Squads... --set 158023 overallrating=99 finishing=99

# Apply changes and create a timestamped save
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save

# Save to a specific new file
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save-as boosted.sav

# Change a player's club and shirt number
python main.py C:\path\to\Squads... --set-team 158023 47 10 --save

# Edit a trait bit: player_id bank bit on|off
python main.py C:\path\to\Squads... --set-trait 158023 1 6 on --save

# Export to Excel
python main.py C:\path\to\Squads... --export squad.xlsx
python main.py C:\path\to\Squads... --export-players players.xlsx
```

Common fields:

```text
overallrating, potential, finishing, dribbling, sprintspeed,
shotpower, ballcontrol, acceleration, agility, stamina, strength,
crossing, shortpassing, longpassing, volleys, composure,
preferredposition1, preferredfoot, weakfootabilitytypecode, skillmoves
```

Fields may also use FC26 short names, such as `BAPc=4` or `aOBn=5`. Values outside the valid range are clamped automatically; use `overallrating=+5` for a relative change.

Show all options:

```powershell
python main.py --help
```

---

## Troubleshooting

### Save not found

Clicking **Open save** opens the file dialog directly in the FC26 save folder. If it looks empty, make sure the game has saved a squad file. See **Opening a save** above for the default folder.

### Dependency installation failed

Make sure Python is installed, then run this from the project folder:

```powershell
python -m pip install -r requirements.txt
```

### Browser cannot connect

Keep the startup window open and visit `http://127.0.0.1:8765/` manually. Closing the command window stops the editor service.

### Peak restore reports missing data

`data/fifa19_peak.csv` ships with the repository, so this should not normally happen. If the file is missing, regenerate it with `python tools/export_fifa19_peak.py`, which needs additional FIFA19 data sources.

---

## License

The original source code and documentation in this project are licensed under the [Apache License 2.0](LICENSE).

Bundled game-derived data, database schema files, player names, player head images, and other third-party materials may be subject to the copyrights and terms of their respective owners. Apache License 2.0 does not transfer those third-party rights.
