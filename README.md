# 我的桌面导师

一个可配置的桌面导师 / 桌宠应用。主程序是 PySide6 写的透明置顶贴纸窗口，支持鼠标和触屏拖动、贴纸旁按钮对话/设置、空闲提醒、文件/文件夹拖放、OpenAI-compatible agent 接口，以及 Windows 打包。

## 目录

根目录现在只保留核心入口和一级分类目录：

- `desktop_mentor.py`：主源码。
- `requirements.txt`：源码运行依赖。
- `assets/`：必要默认素材。
- `scripts/`：Linux / Windows 启动和打包脚本。
- `packaging/`：Linux `.desktop` 和 Windows PyInstaller 配置。
- `docs/`：平台说明文档。
- `README.md`：本说明。
- `.gitignore`：忽略 Python 缓存、Windows 日志、PyInstaller 输出。

关键文件：

- `assets/default_mentor.png`：默认桌宠形象。
- `assets/desktop_mentor.ico`：由默认 PNG 自动生成的 Windows exe 图标。
- `requirements.txt`：源码运行依赖。
- `scripts/linux/run_desktop_mentor.sh`：Linux 启动脚本。
- `scripts/windows/run_desktop_mentor.bat`：Windows 源码运行脚本。
- `scripts/windows/run_desktop_mentor_quiet.vbs`：Windows 无控制台启动入口。
- `scripts/windows/build_windows_exe.bat`：Windows PyInstaller 打包脚本。
- `packaging/windows/desktop_mentor.spec`：Windows PyInstaller 配置。
- `packaging/windows/requirements-windows.txt`：Windows 打包依赖。
- `packaging/linux/desktop_mentor.desktop`：Linux 桌面启动模板。
- `docs/WINDOWS.md`：Windows 使用说明。

已清理掉旧生成素材、预览图、临时 helper 和 Python bytecode 缓存；必要默认素材以 `assets/default_mentor.png` 为准，`assets/desktop_mentor.ico` 可由程序自动生成。

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

如果系统 Python 的 PySide6 不完整，可以指定解释器：

```bash
DESKTOP_MENTOR_PYTHON=/path/to/python ./scripts/linux/run_desktop_mentor.sh
```

自测：

```bash
QT_QPA_PLATFORM=offscreen ./scripts/linux/run_desktop_mentor.sh --self-test
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

打包脚本会先把 `assets/default_mentor.png` 自动转换成 `assets/desktop_mentor.ico`，再执行 PyInstaller。

输出文件：

```text
dist\MyDesktopMentor.exe
```

## 设置

右键桌宠打开 `Agent 设置`。可配置：

- `Agent URL`
- `API Key`
- `Model`
- `Pet image`
- `Click message`
- `Idle message`
- `Idle reminder`
- `Idle mode`
- `Style prompt`

贴纸右侧也有两个圆形按钮：上方打开设置，下方打开对话。对话框会贴近桌宠显示，并自动避开屏幕边界。

用户提供 PNG 形象时，程序会在用户配置目录下自动缓存对应 ICO；默认 PNG 可手动转换：

```bash
python3 desktop_mentor.py --make-icon /path/to/source.png /path/to/output.ico
```

运行时配置保存在系统用户配置目录：

- Linux: `~/.config/my-desktop-mentor/config.json`
- Windows: `%APPDATA%\MyDesktopMentor\config.json`
- macOS: `~/Library/Application Support/MyDesktopMentor/config.json`

也可以用环境变量覆盖配置文件位置：

```bash
DESKTOP_MENTOR_CONFIG=/path/to/config.json ./scripts/linux/run_desktop_mentor.sh
```

## 验证

已验证：

- `python3 -m py_compile desktop_mentor.py`
- `python3 desktop_mentor.py --ensure-default-icon --force-icon`
- `bash -n scripts/linux/run_desktop_mentor.sh`
- `QT_QPA_PLATFORM=offscreen ./scripts/linux/run_desktop_mentor.sh --self-test`
- `desktop-file-validate packaging/linux/desktop_mentor.desktop`
- `python3 -m py_compile packaging/windows/desktop_mentor.spec`
- offscreen 设置/运行时 smoke test
- 最终文件列表只包含源码、必要素材、运行/打包脚本、依赖文件和文档。

## 边界

- API key 只写入用户本机运行时配置，不写入项目目录。
- `work/` 仍是本地任务目录，不同步进 Codex 主仓库。
