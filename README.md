# 我的桌面导师

PySide6 桌面导师 / 桌宠应用。它以透明置顶贴纸停留在桌面上，支持对话、动作贴纸、待办提醒、文件拖放、本地多会话管理、可选模型上下文，以及需要用户授权的电脑控制。

## 功能

- 桌宠贴纸：透明置顶，支持鼠标/触屏拖动、右键菜单和快捷按钮。
- 动作动画：内置 `idle`、`tap`、`drag`、`thinking`、`speaking`、`alert`、`drop_file`、`error` 八类贴纸。
- 对话管理：本地多会话、会话搜索、会话栏/工具栏折叠。
- 模型上下文：可逐次选择是否把当前会话摘要和最近消息发给 agent；关闭时会开启新的独立会话。
- 电脑控制：读取、列目录、搜索、打开、运行、创建/写入文件都走统一授权流程。
- 桌面辅助：文件拖放上下文、待办提醒、配置化形象和话术。

## 安装

要求：

- Python 3.11+
- PySide6 6.5+

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

## Linux 使用

启动：

```bash
cd my-desktop-mentor
./scripts/linux/run_desktop_mentor.sh
```

指定 Python：

```bash
DESKTOP_MENTOR_PYTHON=/usr/bin/python3 ./scripts/linux/run_desktop_mentor.sh
```

诊断和自测：

```bash
./scripts/linux/run_desktop_mentor.sh --diagnose --self-test
./scripts/linux/self_test.sh
```

如果桌面启动器里 fcitx 中文输入无效，可以在 `.desktop` 的 `Exec` 前加：

```ini
Exec=env QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx GTK_IM_MODULE=fcitx SDL_IM_MODULE=fcitx DESKTOP_MENTOR_IM_MODULE=fcitx /opt/my-desktop-mentor/scripts/linux/run_desktop_mentor.sh
```

Linux 桌面启动模板：

```text
packaging/linux/desktop_mentor.desktop
```

复制到 `~/.local/share/applications/` 前，按实际路径修改 `Exec` 和 `Icon`。

## Windows 使用

源码运行：

```bat
scripts\windows\run_desktop_mentor.bat
```

无控制台启动：

```bat
scripts\windows\run_desktop_mentor_quiet.vbs
```

打包 exe：

```bat
scripts\windows\build_windows_exe.bat
```

输出：

```text
dist\MyDesktopMentor.exe
```

Windows 详细说明见 [docs/WINDOWS.md](docs/WINDOWS.md)。

## 基本操作

桌宠右侧快捷按钮：

- 对话
- 设置
- 退出

右键桌宠可以打开设置、待办、文件摘要等操作。

设置页常用项：

- `Agent URL`
- `API Key`
- `Model`
- `Config directory`
- `Pet image`
- `Sticker speed`
- `Action stickers`
- `模型上下文`
- `Computer control`
- `Workspace`
- `Style prompt`

## 动作贴纸

默认素材：

```text
assets/stickers/
```

自定义素材目录格式：

```text
stickers/
  idle/*.png
  tap/*.png
  drag/*.png
  thinking/*.png
  speaking/*.png
  alert/*.png
  drop_file/*.png
  error/*.png
```

命令行导入：

```bash
python3 desktop_mentor.py --load-sticker-dir /path/to/stickers
```

## 会话与上下文

本地会话历史和模型上下文是两套机制：

- 本地会话历史负责保存、搜索和切换多个会话。
- 模型上下文只决定本次请求是否携带当前会话内容给 agent。
- 模型回复支持 Markdown 渲染，用户输入按普通文本显示。

关闭 `使用当前会话上下文` 后，本次输入会进入新的独立会话；旧会话仍保留在本地历史中。

## 电脑控制

常用命令：

```text
/sys 或 /pwd
/ls [路径]
/read <路径>
/search <关键词> [路径]
/open <路径或URL>
/run [--cwd 路径] <命令 参数...>
/mkdir <路径>
/touch <路径>
/write <路径> :: <内容>
/append <路径> :: <内容>
```

自然语言也可以触发授权卡，例如：

```text
请读取 D:\DATA\Desktop\Nature_manuscript.txt
请在桌面创建一个文件 mentor-note.txt，内容是 hello
```

agent 回复中如果包含：

```text
CONTROL_REQUEST: 读取 D:\DATA\Desktop\Nature_manuscript.txt
```

也会生成同一套授权卡。点击 `允许本次` 后才会执行；点击 `拒绝` 不会动手。

安全边界：

- 不支持删除文件。
- 打开、运行、创建、写入都需要用户确认。
- 不执行 `cmd /c`、`powershell -Command`、`sh -c` 这类 shell 字符串命令。
- 敏感路径会被阻止，例如包含 token、secret、password、credential、SSH 私钥等名称的路径。

## 配置位置

运行时配置保存在用户配置目录，不写入项目目录：

- Linux: `~/.config/my-desktop-mentor/`
- Windows: `%APPDATA%\MyDesktopMentor\`
- macOS: `~/Library/Application Support/MyDesktopMentor/`

主要运行时文件：

- `config.json`
- `conversations/`
- `memory.jsonl`
- `todos.json`
- `control/audit.jsonl`

覆盖配置路径：

```bash
DESKTOP_MENTOR_CONFIG=/path/to/config.json ./scripts/linux/run_desktop_mentor.sh
```

## 自测

```bash
./scripts/linux/self_test.sh
python3 -m py_compile desktop_mentor.py
```
