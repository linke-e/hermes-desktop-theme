# Hermes Desktop Theme

从一张参考图生成 Hermes Desktop 的完整主题：颜色主题、背景图、CDP 注入器、变量强制覆盖和安全启动器。

本项目只面向 Hermes Desktop（Electron），不修改 Hermes 应用包、`app.asar`、签名、API Key 或模型供应商配置。Hermes TUI 的 YAML 皮肤是另一套系统。

## 快速开始

需要已安装 Hermes Desktop 和 Python 3。建议使用 Hermes 自带的 Python 环境，以便使用 `websockets`。

```bash
python3 scripts/generate_theme.py \
  --image /absolute/path/to/reference.png \
  --name my-theme \
  --output-dir "$HOME/.hermes/desktop-plugins"
```

生成器会输出三个候选主题：`my-theme-dark`、`my-theme-light` 和 `my-theme-vivid`。选择一个后运行它的 `launcher.sh`：

```bash
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

如果 Hermes Desktop 不在默认路径，可以显式指定：

```bash
HERMES_BIN="/absolute/path/to/Hermes" \
HERMES_DEBUG_PORT=9341 \
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

启动器会直接调用 Hermes 二进制，拒绝占用中的 CDP 端口，不会使用 `open --args`，也不会用宽泛的 `pkill -9` 终止其他进程。

## 生成内容

每个候选主题包含：

- `plugin.js`：Hermes Desktop Plugin SDK 颜色与字体主题
- `inject.css`：`--theme-*`、`--ui-*`、`--dt-*` 三层变量和背景层
- `inject.py`：本机回环 CDP 注入与移除
- `force_vars.py`：压过 Settings 主题选择的 inline `!important` 变量
- `launcher.sh`：Apple Silicon/Intel 路径发现与启动验证
- `assets/bg.png`：背景图副本

## 设计铁律

- 不能把 `--dt-background` 设为 `transparent`。
- 必须覆盖 `--ui-accent`、`--ui-ring`、`--ring` 和 `--dt-composer-ring`。
- 用户气泡默认使用约 10% 透明度，不使用模糊遮罩。
- 禁止宽泛 Tailwind 选择器，例如 `[class*="bg-("]`。
- CDP 只允许 `127.0.0.1`，并且不能把令牌、私聊截图或应用包提交到仓库。
- CSS 注入成功不等于主题验收完成；必须检查 computed styles，并查看真实首页和任务页截图。

完整流程、验证清单和故障处理见 [SKILL.md](./SKILL.md)。

## 自测

```bash
./tests/run-tests.sh
HERMES_THEME_TEST_IMAGE=/absolute/path/to/reference.png ./tests/run-tests.sh
```

## 项目结构

```text
hermes-desktop-theme/
├── SKILL.md
├── scripts/
│   ├── generate_theme.py
│   ├── inject.py
│   ├── force_vars.py
│   └── launcher.sh
├── presets/
└── LICENSE
```

## 许可证

MIT
