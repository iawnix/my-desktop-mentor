# TODO: 我的桌面导师

当前状态：项目已经是可运行原型，核心能力包括透明桌宠、拖动、对话、设置、待办、空闲提醒、文件拖放、OpenAI-compatible agent、可选本地记忆和 Windows 打包。P1 单文件拆分已完成，下一步优化重点不是继续堆功能，而是提高真实使用体验和发布可靠性。

## P0: 先稳住当前基线

- [x] 确认并保留 `desktop_mentor.py` 视觉重做改动，已在提交 `4b9ba93` 保留。
- [x] 修复 Linux 启动脚本的 Python 解释器发现逻辑；优先使用 `.venv`、`CONDA_PREFIX`、系统 Python 和常见用户 conda 路径，并验证 `PySide6.QtCore`。
- [x] 给 `scripts/linux/run_desktop_mentor.sh` 增加更清晰的诊断输出：实际选择的 Python、PySide6 路径、Qt platform、DISPLAY / WAYLAND_DISPLAY。
- [x] 增加 `scripts/linux/self_test.sh`，固定运行语法检查、offscreen self-test、desktop-file 校验、Windows spec 语法检查和 Qt smoke test。
- [x] 检查并补充 `.gitignore`，覆盖运行日志、PyInstaller 输出、Python 缓存、用户配置、临时文件和截图目录。

## P1: 拆分单文件架构

`desktop_mentor.py` 已超过 2600 行。继续单文件开发会让 UI、agent、配置、存储和平台兼容逻辑互相缠住。

- [x] 建立包结构 `desktop_mentor_app/`，根目录 `desktop_mentor.py` 保留为薄 CLI 入口。
- [x] 拆出 `config_store.py`：`AgentConfig`、默认值、配置目录指针、配置读写、配置迁移。
- [x] 拆出 `todo_store.py`：待办读写、清洗、排序、到期过滤。
- [x] 拆出 `agent_client.py`：OpenAI-compatible URL 归一化、请求、错误处理、本地 fallback、记忆拼接。
- [x] 拆出 `drop_context.py`：文件/文件夹描述、文本预览、大小限制、敏感文件跳过规则。
- [x] 拆出 `idle_detector.py`：Windows idle、GNOME idle、xprintidle fallback。
- [x] 拆出 `ui/dialogs.py`：设置、对话、待办、满屏提醒。
- [x] 拆出 `ui/pet_widget.py`：透明桌宠窗口、绘制、拖动、触摸、按钮、bubble 布局。
- [x] 拆出 `assets.py`：资源路径、ICO 生成和缓存路径。

## P2: 让文件拖放真的进入导师对话

当前 drop 已能读取文件上下文并保存在运行时字段里，但对话请求没有自动带上这些上下文。

- [x] 拖入文件后，在下一次对话中自动附加 `last_drop_context`，并在对话框显示上下文已附加。
- [x] 增加“只问文件 / 清除文件上下文 / 文件摘要”的右键入口。
- [x] 默认跳过敏感文件名：`.env`、`id_rsa`、`token`、`secret`、`password`、`credentials`。
- [x] 默认跳过 `.git/`、缓存目录、构建产物和二进制正文预览。
- [x] 对多文件夹 drop 加摘要优先级：README、Markdown、Python、配置文件优先，图片/二进制只列元信息。

## P3: 暂不做 - 降低提醒打扰感

Decision: 暂不做。用户当前判断 P3 没必要，并且该方向会削弱“idle 达到阈值后每 5 秒持续提醒直到用户操作”的既定行为。

- [x] 保留当前 idle 提醒强度：达到阈值后持续提醒，直到用户有操作。
- [ ] 暂不增加 cooldown、稍后提醒、工作时段、勿扰模式、snooze、重复规则或满屏提醒强度分级。

## P4: 改善 agent 体验

- [x] 待办提醒改为确认制：提醒泡泡不自动消失，点击后才删除待办；未点击时按配置间隔重新排队并累计泡泡。
- [x] 对话框升级为会话管理器：左侧会话列表，右侧当前会话记录，发送后不关闭窗口，并显示处理中 / 就绪状态。
- [x] 增加本地记忆机制：每个会话独立 JSONL，维护会话摘要和记忆条目；打开 `Memory` 后把当前会话上下文注入 agent 请求。
- [x] 增加本地 agent 状态账本：`agent_state.sqlite3` 记录任务运行、电脑控制工具证据和待确认记忆候选；请求前由 context assembler 统一注入相关任务状态。
- [x] 请求处理中提供取消入口，取消后恢复发送状态并把取消结果写入当前会话。
- [x] 支持更长回复的详情窗口；bubble 只显示摘要，对话卡片提供“完整回复”入口。
- [ ] 对话失败后提供窗口内重试入口。
- [ ] agent 请求超时后的明确重试入口和错误分类。
- [ ] 可选启用 streaming。
- [ ] 记忆管理增加“导出记忆 / 编辑记忆 / 跨会话稳定记忆晋升 / 记忆候选收件箱”。
- [ ] API key 保存前提示其只写入用户配置目录，不写入项目目录。

## P5: 桌面体验和跨平台发布

- [x] 增加动作贴纸系统：`idle`、`tap`、`drag`、`thinking`、`speaking`、`alert`、`drop_file`、`error` 八类动作可在设置里按顺序选择多张图片；默认使用项目内置 `assets/stickers/`，无素材时回退到默认静态形象。
- [ ] Linux `.desktop` 的 `Exec` 路径需要安装/复制流程，不能只适合当前源码目录。
- [x] 增加托盘图标和菜单入口，防止桌宠被隐藏、遮挡或移出屏幕后难以找回。
- [ ] 保存窗口位置、尺寸和最近屏幕，重启后恢复。
- [ ] 多显示器下，`回到右下角` 应回到当前屏幕或主屏幕可配置。
- [ ] Windows build 脚本增加 Python、pip、PyInstaller 版本输出。
- [ ] Windows 打包后做一次真实 exe smoke test，并记录验证结果。
- [ ] README 增加“源码运行”和“打包运行”的最短路径，减少解释器问题。

## P6: 测试与验证门

- [ ] 单元测试：`normalize_chat_url`、配置读写、配置迁移、todo 读写、drop context 截断、ICO 生成。
- [ ] Qt offscreen smoke test：主窗口创建、设置弹窗创建、对话弹窗创建、待办弹窗创建。
- [ ] 交互 smoke test：模拟设置保存、todo 添加/删除、bubble 长文本布局。
- [ ] 启动脚本验证：无 `DESKTOP_MENTOR_PYTHON`、有 `DESKTOP_MENTOR_PYTHON`、无 display、offscreen。
- [ ] 发布前固定运行：

```bash
python3 -m py_compile desktop_mentor.py
bash -n scripts/linux/run_desktop_mentor.sh
DESKTOP_MENTOR_PYTHON=/home/iaw/soft/conda/2026.03.05/bin/python3 QT_QPA_PLATFORM=offscreen ./scripts/linux/run_desktop_mentor.sh --self-test
desktop-file-validate packaging/linux/desktop_mentor.desktop
python3 -m py_compile packaging/windows/desktop_mentor.spec
```

## 边界

- 不把 API key、对话记忆、todo 数据或用户文件内容写入项目目录。
- 不把 `work/` 项目自动同步到 Codex 主仓库。
- 不在未确认前发布到远端仓库或生成公开 release。
- 不把“导师”人格改成羞辱、PUA 或强压式话术；默认应是清晰、直接、可靠的科研协助。

## 建议下一步

P0、P1、P2 已收口，P4 已补上请求取消和长回复详情。下一步优先做 P5 的托盘/窗口位置/安装路径，再补 P4 的失败重试和 P6 的单元测试。
