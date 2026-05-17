# 我的桌面导师

一个可配置的桌面导师 / 桌宠应用。主程序是 PySide6 写的透明置顶贴纸窗口，支持鼠标和触屏拖动、动作贴纸动画、贴纸旁按钮对话/设置/退出、右键待办提醒、空闲提醒、文件/文件夹拖放、OpenAI-compatible agent 接口、可选本地对话记忆、受控电脑操作，以及 Windows 打包。

## 目录

根目录现在只保留核心入口和一级分类目录：

- `desktop_mentor.py`：CLI 入口，只负责参数解析、Qt 应用启动和 self-test 输出。
- `desktop_mentor_app/`：应用包，包含配置、资源、动作贴纸、agent、待办、idle 检测、drop 上下文和 UI 组件。
- `requirements.txt`：源码运行依赖。
- `assets/`：必要默认素材。
- `scripts/`：Linux / Windows 启动和打包脚本。
- `packaging/`：Linux `.desktop` 和 Windows PyInstaller 配置。
- `docs/`：平台说明文档。
- `README.md`：本说明。
- `.gitignore`：忽略 Python 缓存、Windows 日志、PyInstaller 输出。

关键文件：

- `assets/cow.png`：默认桌宠形象。
- `assets/desktop_mentor.ico`：由默认 PNG 自动生成的 Windows exe 图标。
- `assets/todo_badge.png`：待办窗口图标。
- `assets/stickers/`：默认动作贴纸素材，包含 `idle`、`tap`、`drag`、`thinking`、`speaking`、`alert`、`drop_file`、`error` 八类动作，每类 8 帧。
- `desktop_mentor_app/config_store.py`：运行时配置、配置目录切换、配置迁移和记忆/待办路径。
- `desktop_mentor_app/control/`：受控电脑操作层，包含命令解析、权限判断、跨平台执行器和审计日志。
- `desktop_mentor_app/assets.py`：默认资源路径、PNG 到 ICO 转换、用户图标缓存。
- `desktop_mentor_app/conversation_store.py`：本地会话索引、每会话消息 JSONL、摘要/记忆条目和旧历史迁移。
- `desktop_mentor_app/stickers.py`：动作贴纸集清洗、顺序保留和帧数量统计。
- `desktop_mentor_app/agent_client.py`：OpenAI-compatible URL 归一化、请求、本地 fallback 和可选记忆拼接。
- `desktop_mentor_app/todo_store.py`：待办清洗、排序、读写和到期过滤。
- `desktop_mentor_app/idle_detector.py`：Windows、GNOME、xprintidle 空闲时间检测。
- `desktop_mentor_app/drop_context.py`：文件/文件夹拖放上下文收集、敏感路径跳过和 prompt 拼接。
- `desktop_mentor_app/ui/dialogs.py`：设置、对话、详情、待办和满屏提醒窗口。
- `desktop_mentor_app/ui/pet_widget.py`：透明桌宠窗口、绘制、鼠标/触屏拖动、按钮、菜单和 bubble 布局。
- `requirements.txt`：源码运行依赖。
- `scripts/linux/run_desktop_mentor.sh`：Linux 启动脚本。
- `scripts/linux/self_test.sh`：Linux 一键自测脚本。
- `scripts/windows/run_desktop_mentor.bat`：Windows 源码运行脚本。
- `scripts/windows/run_desktop_mentor_quiet.vbs`：Windows 无控制台启动入口。
- `scripts/windows/build_windows_exe.bat`：Windows PyInstaller 打包脚本。
- `packaging/windows/desktop_mentor.spec`：Windows PyInstaller 配置。
- `packaging/windows/requirements-windows.txt`：Windows 打包依赖。
- `packaging/linux/desktop_mentor.desktop`：Linux 桌面启动模板。
- `docs/WINDOWS.md`：Windows 使用说明。

已清理掉旧生成素材、预览图、临时 helper 和 Python bytecode 缓存；必要默认素材以 `assets/cow.png` 为准，`assets/desktop_mentor.ico` 可由程序自动生成。

## Linux 使用

源码运行：

```bash
cd my-desktop-mentor
./scripts/linux/run_desktop_mentor.sh
```

直接用 Python 运行也可以，但需要当前 Python 能导入 `PySide6`：

```bash
python3 desktop_mentor.py
```

默认桌宠显示尺寸是 `220 px`。如果临时想更大，可以用 `--size 280`；右键菜单里的 `放大` / `缩小` 支持在 `72-560 px` 范围内调整。

如果系统 Python 的 PySide6 不完整，可以指定解释器：

```bash
DESKTOP_MENTOR_PYTHON=/path/to/python ./scripts/linux/run_desktop_mentor.sh
```

自测：

```bash
./scripts/linux/self_test.sh
```

启动脚本也支持只看诊断信息，便于定位 Python / Qt / 显示环境问题：

```bash
./scripts/linux/run_desktop_mentor.sh --diagnose --self-test
```

## Windows 使用

源码运行：

```bat
scripts\windows\run_desktop_mentor.bat
```

这个脚本会检查 Python 和 PySide6；缺少 PySide6 时会自动执行：

```bat
python -m pip install -r requirements.txt
```

无控制台启动：

```bat
scripts\windows\run_desktop_mentor_quiet.vbs
```

打包 exe：

```bat
scripts\windows\build_windows_exe.bat
```

打包脚本会先把 `assets/cow.png` 自动转换成 `assets/desktop_mentor.ico`，再执行 PyInstaller。

输出文件：

```text
dist\MyDesktopMentor.exe
```

## 设置

右键桌宠打开 `Agent 设置`。可配置：

- `Agent URL`
- `API Key`
- `Model`
- `Config directory`
- `Pet image`
- `Action stickers`
- `Click message`
- `Idle message`
- `Drop message`
- `Message duration`
- `Todo repeat`
- `Idle reminder`
- `Idle mode`
- `Memory`
- `Memory depth`
- `Computer control`
- `Workspace`
- `Style prompt`

贴纸右侧有三个圆形按钮，从上到下是：对话、设置、退出。对话窗口会贴近桌宠显示，并自动避开屏幕边界。

默认人格是友好的科研导师。这个项目本身是桌面导师框架，用户可以通过设置修改形象、话术、空闲提醒、drop 行为和 style prompt，形成自己的导师桌宠。

`Action stickers` 默认使用项目内置的 `assets/stickers/`，支持 8 类动作素材，设置页会按动作分组录入图片路径，并按行顺序播放：

- `idle`
- `tap`
- `drag`
- `thinking`
- `speaking`
- `alert`
- `drop_file`
- `error`

每个动作建议准备约 8 张图片；程序不强制数量，1 张会作为静态动作，多张会按 `120 ms/frame` 循环播放。没有用户自定义动作素材时，程序会优先使用项目内置 `assets/stickers/`；若内置素材不可用，再回退到 `Pet image` 或默认 `assets/cow.png`。后续替换素材时，可以在设置页点 `导入动作目录` 选择包含上述 8 个子目录的素材根目录，也可以在对应动作里用“按顺序选择”，或手动按每行一张路径排列。

命令行导入动作目录：

```bash
python3 desktop_mentor.py --load-sticker-dir /path/to/stickers
```

素材目录格式：

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

对话窗口是本地会话管理器：左侧列出历史会话，右侧显示当前会话记录和本地摘要/记忆提示。新会话、切换会话、清空当前会话都只操作用户配置目录，不写入项目目录。存储位置是 `conversations/sessions.json`、`conversations/active_session.txt` 和每个会话自己的 `conversations/<session-id>.jsonl`；首次升级时会把旧的 `chat_history.jsonl` 或 `memory.jsonl` 迁移成一个会话。

启用 `Memory` 后，程序会把当前会话摘要、命中的记忆条目和最近若干轮消息作为上下文带给 agent；同时保留旧 `memory.jsonl` 作为兼容记忆。默认关闭，不会把历史无条件发给模型，也不会写入项目目录。

启用 `Computer control` 后，对话窗口支持受控电脑操作。读操作会直接执行；运行命令、打开路径/链接、创建或写入文件会先在会话里显示授权卡片，用户点击 `授权执行` 后才动手，点击 `取消` 则不会执行。明确的自然语言请求也会走同一套授权流程，例如“请在桌面创建一个文件 `mentor-note.txt`，内容是「hello」”。

支持的第一阶段/第二阶段命令：

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

`Workspace` 是相对路径和命令运行的默认工作目录。第一版不会执行删除类命令，不通过 shell 字符串执行任意命令，也会阻止读取或写入看起来包含 token、secret、password、credential、SSH 私钥等敏感名称的路径。电脑操作审计日志写入运行时配置目录的 `control/audit.jsonl`。

`Config directory` 可以切换运行时设置目录；`config.json`、`conversations/`、`control/audit.jsonl`、`chat_history.jsonl`、`memory.jsonl`、`todos.json` 和自动生成的图标缓存都会跟着这个目录走。

右键菜单里的 `待办` 可以添加定时提醒。时间输入框固定为 `年-月-日 时:分:秒` 格式，可直接输入数字。待办到期后会在桌面上生成持久提醒泡泡；泡泡默认不自动消失，点击任意一个同待办泡泡后才确认并删除该待办。若一直不点击，程序会按 `Todo repeat` 间隔移除旧到期事件并追加下一次待办提醒，桌面上会保留累计提醒泡泡。待办泡泡存在时会压制 idle 提醒，避免两套机制同时弹出。

拖放文件或文件夹到桌宠后，下一次对话会显示文件上下文 chip；用户可以勾选是否加载到本次对话，也可以点 `x` 直接移除。右键菜单会出现 `只问文件`、`文件摘要`、`清除文件上下文`。拖放预览会跳过 `.env`、token、secret、password、credential、SSH 私钥名，以及 `.git/`、缓存目录和构建产物。

用户提供 PNG 形象时，程序会在用户配置目录下自动缓存对应 ICO；默认 PNG 可手动转换：

```bash
python3 desktop_mentor.py --make-icon /path/to/source.png /path/to/output.ico
```

运行时配置保存在系统用户配置目录：

- Linux: `~/.config/my-desktop-mentor/config.json`
- Windows: `%APPDATA%\MyDesktopMentor\config.json`
- macOS: `~/Library/Application Support/MyDesktopMentor/config.json`

程序启动时会优先继承已有配置：环境变量指定的位置优先，其次是已保存的 `Config directory` 指针；如果指针目录还没有 `config.json`，会继续扫描系统默认配置目录和旧版本配置目录，找到已有 `config.json` 就直接沿用。

也可以用环境变量覆盖配置文件位置：

```bash
DESKTOP_MENTOR_CONFIG=/path/to/config.json ./scripts/linux/run_desktop_mentor.sh
```

## 验证

已验证：

- `python3 -m py_compile desktop_mentor.py`
- `python3 desktop_mentor.py --ensure-default-icon --force-icon`
- `bash -n scripts/linux/run_desktop_mentor.sh`
- `bash -n scripts/linux/self_test.sh`
- `QT_QPA_PLATFORM=offscreen ./scripts/linux/run_desktop_mentor.sh --self-test`
- `desktop-file-validate packaging/linux/desktop_mentor.desktop`
- `python3 -m py_compile packaging/windows/desktop_mentor.spec`
- `./scripts/linux/self_test.sh`
- offscreen 设置/内置动作贴纸/会话管理/记忆上下文/运行时 smoke test
- 受控电脑操作命令解析、只读执行、确认型写入/运行命令、阻止删除命令回归测试
- 最终文件列表只包含源码、必要素材、运行/打包脚本、依赖文件和文档。

## 边界

- API key 只写入用户本机运行时配置，不写入项目目录。
- 会话索引、会话历史、对话记忆和待办只写入用户配置目录，不写入项目目录。
- 待办只写入用户配置目录的 `todos.json`，不写入项目目录。
- 电脑操作审计日志只写入用户配置目录的 `control/audit.jsonl`，不写入项目目录。
- 第一版电脑操作不支持删除文件、force 操作、shell 字符串执行或无确认写入；运行、打开和写入都需要用户在对话窗口确认。
- 项目内置贴纸素材保存在 `assets/stickers/`；用户后续导入的外部素材只以路径形式写入运行时配置，除非明确要求打包进项目。
- `work/` 仍是本地任务目录，不同步进 Codex 主仓库。
