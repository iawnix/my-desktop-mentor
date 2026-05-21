# 我的桌面导师

PySide6 桌面导师 / 桌宠应用。它以透明置顶贴纸停留在桌面上，支持对话、动作贴纸、待办提醒、文件拖放、本地多会话管理、可选模型上下文，以及需要用户授权的电脑控制。

## 功能

- 桌宠贴纸：透明置顶，支持鼠标/触屏拖动、右键菜单、托盘入口和快捷按钮。
- 动作动画：内置 `idle`、`tap`、`drag`、`thinking`、`speaking`、`alert`、`drop_file`、`error` 八类贴纸。
- 对话管理：本地多会话、会话搜索、会话栏/工具栏折叠。
- 交互状态：请求处理中可取消，长回复可在独立详情窗口查看。
- 模型上下文：可逐次选择是否把当前会话摘要、最近消息和用户长期记忆发给 agent；关闭时会开启新的独立会话。
- 长期记忆：本地保存用户级偏好/约束，支持在对话窗口中查看、编辑、停用和删除。
- 电脑控制：读取、列目录、搜索、打开、运行、创建/写入文件都走统一授权流程。
- 桌面辅助：文件拖放上下文、待办提醒、配置化形象和话术。

## 安装

要求：

- Conda / Miniconda / Anaconda
- Python 3.11+（推荐由 Conda 环境提供）
- PySide6 6.5+

Linux 推荐直接运行用户级安装脚本。它会创建项目本地 Conda 环境、安装依赖，并把实际路径的桌面启动器写入 `~/.local/share/applications/`，这样 rofi 可以直接启动。

```bash
bash install_linux.sh
```

Windows:

```bat
scripts\windows\setup_conda_env.bat
```

Linux 安装脚本常用选项：

```bash
bash install_linux.sh --conda /path/to/conda
bash install_linux.sh --env-prefix "$PWD/.conda"
bash install_linux.sh --env-name my-desktop-mentor
bash install_linux.sh --python-version 3.12
bash install_linux.sh --input-method auto
bash install_linux.sh --qt-platform auto
bash install_linux.sh --no-deps
bash install_linux.sh --dry-run
```

安装脚本默认会自动探测当前机器的输入法和桌面环境，再生成 `.desktop`：

- 输入法：`auto`、`fcitx`、`ibus`、`none`
- Qt 平台：`auto`、`xcb`、`wayland`、`none`
- Conda：可用 `--conda /path/to/conda` 指定用户自己的 Conda 可执行文件
- 环境：可用 `--env-prefix /path/to/env` 创建路径环境，或 `--env-name name` 创建命名环境

例如用户已经安装了 Miniconda，想创建命名环境并适配 Wayland + IBus：

```bash
bash install_linux.sh \
  --conda "$HOME/miniconda3/bin/conda" \
  --env-name my-desktop-mentor \
  --input-method ibus \
  --qt-platform wayland
```

如果只想安装或修复 Conda 依赖，不写入桌面启动器：

```bash
./scripts/linux/setup_conda_env.sh
```

也可以手动创建命名环境：

```bash
conda create -n my-desktop-mentor python=3.12 pip
conda run -n my-desktop-mentor python -m pip install -r requirements.txt
```

启动脚本会按顺序查找：

- `DESKTOP_MENTOR_PYTHON` 指定的解释器
- `DESKTOP_MENTOR_CONDA_PREFIX` 指定的环境
- 项目本地 `.conda/`
- 当前已激活的 `CONDA_PREFIX`
- `DESKTOP_MENTOR_CONDA_ENV_NAME` 指定的命名环境（默认 `my-desktop-mentor`）
- `.venv/` 和系统 Python 作为兜底

## Linux 使用

首次安装：

```bash
cd my-desktop-mentor
bash install_linux.sh
```

如果自动探测不符合当前桌面环境，可以重新生成 `.desktop`，不重新安装依赖：

```bash
bash install_linux.sh --no-deps --input-method fcitx --qt-platform xcb
```

启动：

```bash
cd my-desktop-mentor
./scripts/linux/run_desktop_mentor.sh
```

指定 Python：

```bash
DESKTOP_MENTOR_PYTHON=/usr/bin/python3 ./scripts/linux/run_desktop_mentor.sh
```

指定命名 Conda 环境：

```bash
DESKTOP_MENTOR_CONDA_ENV_NAME=my-desktop-mentor ./scripts/linux/run_desktop_mentor.sh
```

指定 Conda 环境路径：

```bash
DESKTOP_MENTOR_CONDA_PREFIX="$PWD/.conda" ./scripts/linux/run_desktop_mentor.sh
```

诊断和自测：

```bash
./scripts/linux/run_desktop_mentor.sh --diagnose --self-test
./scripts/linux/self_test.sh
```

如果桌面启动器里 fcitx 中文输入无效，可以在 `.desktop` 的 `Exec` 前加：

```ini
Exec=env QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx GTK_IM_MODULE=fcitx SDL_IM_MODULE=fcitx DESKTOP_MENTOR_IM_MODULE=fcitx DESKTOP_MENTOR_CONDA_ENV_NAME=my-desktop-mentor /opt/my-desktop-mentor/scripts/linux/run_desktop_mentor.sh
```

Linux 桌面启动模板：

```text
packaging/linux/desktop_mentor.desktop
```

一般不需要手动复制模板，`bash install_linux.sh` 会生成带实际路径的：

```text
~/.local/share/applications/desktop_mentor.desktop
```

如果使用 rofi 启动，先确认桌面文件可见：

```bash
desktop-file-validate ~/.local/share/applications/desktop_mentor.desktop
gtk-launch desktop_mentor
```

## Windows 使用

首次安装依赖：

```bat
scripts\windows\setup_conda_env.bat
```

源码运行：

```bat
scripts\windows\run_desktop_mentor.bat
```

无控制台启动：

```bat
scripts\windows\run_desktop_mentor_quiet.vbs
```

Windows 启动脚本同样优先使用项目本地 `.conda\python.exe`。如需指定已有环境：

```bat
set DESKTOP_MENTOR_CONDA_PREFIX=C:\Users\you\miniconda3\envs\my-desktop-mentor
scripts\windows\run_desktop_mentor.bat
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
系统托盘菜单也可以显示/隐藏桌宠、打开对话/待办/设置、把桌宠移回右下角或退出。

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
- 用户长期记忆保存在本机 `user_memory.json`，设置中启用后会随模型上下文一起注入。
- 对话窗口左侧的 `记忆` 可以手动新增、编辑、停用或删除长期记忆。
- 模型回复使用 HTML Markdown 渲染，支持代码高亮、表格和 LaTeX 公式；用户输入按普通文本显示。
- 输入框按 Enter 发送消息，Shift+Enter 插入换行。
- 请求处理中可点 `取消` 停止等待；较长的导师回复会显示 `完整回复` 入口。

关闭 `使用当前会话上下文` 后，本次输入会进入新的独立会话；旧会话仍保留在本地历史中。

## 架构

当前代码按 V2 分层组织：

- `constants/`：按领域拆分的应用、模型、桌宠、贴纸、待办、记忆和控制默认值。
- `core/`：qasync 运行时、后台任务执行器、日志和资源/图标辅助。
- `config/`、`state/`：版本化配置迁移、本地会话、记忆和待办状态。
- `model_client/`：OpenAI-compatible 模型客户端和 agent prompt/message 组装。
- `tools/`、`security/`：工具计划、命令解析、拖放文件上下文、自然语言解析、执行、权限策略和审计。
- `pet/`、`cron/`、`platforms/`：桌宠动画、贴纸集合、聊天/控制服务、提醒调度、显示/输入/idle 平台适配和消息平台接口骨架；`pet/` 保持轻量懒加载，避免纯逻辑导入拉起 Qt 依赖。
- `ui/`：Qt 界面、桌宠绘制、交互控制、对话窗口、Markdown 渲染和主题。`ui/dialogs.py` 保留为兼容导出入口，具体实现拆到 `chat_dialog.py`、`settings_dialog.py`、`todo_dialog.py` 等模块。

包根目录只保留 `__init__.py`。历史兼容入口已移除；真实实现统一位于 `constants/`、`model_client/`、`core/`、`config/`、`tools/`、`pet/`、`platforms/`、`state/` 和 `security/`，新增功能应直接依赖这些模块。

运行时日志写入配置目录下的：

```text
logs/app.log
```

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
- `user_memory.json`
- `todos.json`
- `control/audit.jsonl`
- `logs/app.log`

旧版 `config.json` 首次加载时会自动迁移到 `schema_version: 2`，并在同目录生成一次 `config.v1.bak.json` 备份。

覆盖配置路径：

```bash
DESKTOP_MENTOR_CONFIG=/path/to/config.json ./scripts/linux/run_desktop_mentor.sh
```

## 自测

```bash
./scripts/linux/self_test.sh
PYTHONPATH=. python3 -m unittest discover -s tests
python3 -m py_compile desktop_mentor.py
```
