# FC26 存档编辑器

一个面向 Windows 的 EA SPORTS FC 26 `Squads` 存档编辑器。项目结构参考 FIFA19 编辑器，底层读写采用 FC26 的 `FBCHUNKS + DB` 格式；提供中文 Web 界面、命令行和 Excel 导出。

## 功能

- 按姓名、中文名或球员 ID 搜索球员，并按国籍、位置、总评筛选
- 编辑 FC26 的总评、潜力、能力值、位置、角色、惯用脚、逆足、花式、身体数据等字段
- 通过位复选框编辑普通特性与图标特性
- 查看和调整球队阵容、球衣号码
- 在俱乐部与自由球员池之间进行原位转会；国家队关系可单独修改
- 保存前暂存修改、放弃修改；保存后自动重载验证
- 导出完整数据库或 `CZUM` 球员表到 Excel

## 安装和启动

需要 Windows 10/11 与 Python 3.10+。双击 [start_editor.bat](start_editor.bat)，或手动执行：

```powershell
python -m pip install -r requirements.txt
python web_app.py
```

浏览器打开 `http://127.0.0.1:8765/`。启动时会自动查找当前用户 FC26 settings 目录中修改时间最新的 `Squads*` 文件，也可以在页面中输入完整路径打开。

## 命令行

```powershell
# 查看摘要
python main.py C:\path\to\Squads20260902010101

# 搜索和查看球员
python main.py C:\path\to\Squads... --search Messi
python main.py C:\path\to\Squads... --player 158023

# 预览修改；不带保存参数不会写文件
python main.py C:\path\to\Squads... --set 158023 overallrating=99 finishing=99

# 保存为新的时间戳文件，或指定新文件
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save
python main.py C:\path\to\Squads... --set 158023 overallrating=99 --save-as boosted.sav

# 修改球员的现有球队关系和球衣号
python main.py C:\path\to\Squads... --set-team 158023 47 10 --save

# 导出
python main.py C:\path\to\Squads... --export squad.xlsx
python main.py C:\path\to\Squads... --export-players players.xlsx
```

字段既支持完整名称，也支持 4 字节短名，例如 `overallrating=99`、`BAPc=4`、`aOBn=5`。数值会按照 FC26 元数据范围自动限制；花式技巧存档值为 0–4，对应 1–5 星，写入时使用原始值。

## 项目结构

```text
.
├─ web/             Web 页面、样式和 JavaScript
├─ web_app.py       Flask Web 服务与 JSON API
├─ core/            FC26 容器、DB、表、字段和名称解析
├─ services/        球员、球队、阵容和安全保存服务
├─ backend_cli.py   命令行入口
├─ data/            FC26 元数据和名称/球队/国家映射
├─ config/          位置、角色、国籍和 FST 名称映射
├─ tests/            存档往返测试
└─ docs/             存档格式说明
```

保存会在输入存档所在目录生成新的 `SquadsYYYYMMDDHHMMSS` 文件，不覆盖原文件。使用前请备份原始存档，并在游戏中确认新文件可以正常加载。
