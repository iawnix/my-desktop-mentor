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

脚本会先把 `assets\cow.png` 转成 `assets\desktop_mentor.ico`，再开始 PyInstaller 打包。

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

API key、agent URL、style prompt、idle 提醒话术、点击互动话术、drop 话术、消息停留时间、idle 模式、模型上下文默认开关、电脑控制开关、配置目录和桌宠形象路径都是运行时设置，不写入项目目录。用户在设置里选择 PNG 形象时，程序会自动在 `%APPDATA%\MyDesktopMentor\icons` 下缓存对应 ICO。本地多会话历史保存在 `%APPDATA%\MyDesktopMentor\conversations`；启用模型上下文后，兼容记忆还会写入 `%APPDATA%\MyDesktopMentor\memory.jsonl`。右键待办默认保存在 `%APPDATA%\MyDesktopMentor\todos.json`，到期提醒后会自动删除。

## 电脑控制

对话窗口支持受控电脑操作。Windows 下读操作会直接执行；打开路径、运行命令、创建或写入文件会先显示授权卡片，需要点击 `授权执行` 才会动手。明确的自然语言桌面写文件请求也会进入授权流程。操作记录写入：

```text
%APPDATA%\MyDesktopMentor\control\audit.jsonl
```

常用命令：

```text
/sys
/ls C:\Users\you\Desktop
/read notes.txt
/search keyword .
/open C:\Users\you\Desktop
/run --cwd C:\Users\you\project python --version
/write notes.txt :: hello
请在桌面创建一个文件 `mentor-note.txt`，内容是「hello」
```

第一版不支持删除文件，不通过 `cmd /c`、`powershell -Command` 这类 shell 字符串执行任意命令，也会阻止看起来包含 token、secret、password、credential、SSH 私钥等敏感名称的路径。
