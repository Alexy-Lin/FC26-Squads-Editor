# FC26 存档编辑器

EA SPORTS FC 26 `Squads` 存档编辑工具，提供中文 Web 界面、命令行和 Excel 导出功能。

## 功能

- 搜索球员：姓名、中文名或球员 ID
- 按国籍、位置、总评筛选球员
- 球员详情页优先显示内置头像，未匹配到头像时显示姓名首字母
- 修改总评、潜力、能力值、位置、角色、惯用脚、逆足、花式和身体数据
- 修改普通特性和图标特性
- 查看球队阵容，批量修改球衣号码
- 俱乐部、自由球员之间转会
- 导出球员表或完整存档数据到 Excel

## 安装

需要 Windows 10/11 和 Python 3.10 或更高版本。

### 自动安装

双击项目中的 `start_editor.bat`，脚本会自动选择 Python 并安装缺少的依赖。

### 手动安装

在项目目录打开 PowerShell：

```powershell
python -m pip install -r requirements.txt
```

## Web 界面

启动服务：

```powershell
python web_app.py
```

然后打开：

```text
http://127.0.0.1:8765/
```

启动时会自动打开 FC26 存档目录中最新的 `Squads*` 文件。也可以点击“打开存档”，输入存档完整路径。

基本操作：

1. 在“球员编辑”中搜索并选择球员。
2. 修改字段或选择球队、国家队、特性。
3. 点击“应用球员修改”。修改此时只保存在内存中。
4. 确认无误后点击“保存为新存档”。

球队页面可以查看阵容，并批量填写球衣号码。转会页面可以选择来源球队和目标球队，再点击球员对应的转会按钮。

## 命令行

以下命令都在项目目录执行。将示例路径替换为自己的 `Squads` 文件路径。

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

常用字段包括：

```text
overallrating, potential, finishing, dribbling, sprintspeed,
shotpower, ballcontrol, acceleration, agility, stamina, strength,
crossing, shortpassing, longpassing, volleys, composure,
preferredposition1, preferredfoot, weakfootabilitytypecode, skillmoves
```

字段也可以使用 FC26 的短名，例如 `BAPc=4`、`aOBn=5`。数值超出范围时会自动限制到有效范围；相对修改可以写成 `overallrating=+5`。

## 保存和备份

- Web 界面保存会在原存档所在目录生成新的 `SquadsYYYYMMDDHHMMSS` 文件。
- CLI 使用 `--save` 也会生成新的时间戳文件。
- `--save-as` 必须指定一个新的输出路径，程序不会覆盖已有文件。
- 原始存档不会被编辑器覆盖，建议保存前自行备份。
- 保存完成后程序会自动重新读取并验证修改结果。

## 常见问题

### 找不到存档

在“打开存档”中输入完整路径。FC26 默认存档目录通常是：

```text
C:\Users\你的用户名\AppData\Local\EA SPORTS FC 26\settings\
```

文件名一般类似：

```text
Squads20260902010101
```

### 依赖安装失败

确认已安装 Python，并在项目目录手动执行：

```powershell
python -m pip install -r requirements.txt
```

### 浏览器打不开

确认启动窗口仍在运行，然后手动访问 `http://127.0.0.1:8765/`。关闭命令窗口会停止编辑器服务。

## 测试

```powershell
python -m unittest discover -s tests -v
```
