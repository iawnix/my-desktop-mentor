# Windows 使用

## 源码运行

1. 从 python.org 安装 Python 3.11+。
2. 安装时勾选 `Add python.exe to PATH`。
3. 在 Windows 打开本目录。
4. 双击：

```bat
scripts\windows\run_desktop_mentor.bat
```

启动脚本会检查 Python 和 PySide6；缺少 PySide6 时会自动安装 `requirements.txt`。日志写入 `windows-run.log`。

## 无控制台启动

源码运行确认可用后，可以用：

```bat
scripts\windows\run_desktop_mentor_quiet.vbs
```

这个入口会隐藏控制台窗口。

## 编译 EXE

在 Windows 上执行：

```bat
scripts\windows\build_windows_exe.bat
```

脚本会先把 `assets\default_mentor.png` 转成 `assets\desktop_mentor.ico`，再开始 PyInstaller 打包。

输出：

```text
dist\MyDesktopMentor.exe
```

打包日志写入 `windows-build.log`。

## 安装 / 使用

`dist\MyDesktopMentor.exe` 是单文件程序，可以复制到任意目录运行。运行时设置保存在：

```text
%APPDATA%\MyDesktopMentor\config.json
```

API key、agent URL、style prompt、idle 提醒话术、点击互动话术、idle 模式和桌宠形象路径都是运行时设置，不写入项目目录。用户在设置里选择 PNG 形象时，程序会自动在 `%APPDATA%\MyDesktopMentor\icons` 下缓存对应 ICO。
