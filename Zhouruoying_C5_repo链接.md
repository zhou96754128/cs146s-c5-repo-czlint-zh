# C5 仓库链接与可验证性说明

## 1. 仓库地址

**https://github.com/zhou96754128/cs146s-c5-repo-czlint-zh**

| 项 | 值 |
|---|---|
| 可见性 | 公开（`private: false`，未登录即可访问） |
| 默认分支 | `main` |
| 许可证 | MIT |
| 提交 HEAD | `781d90dbb0778dd2d5a2adcf17ddc741d787bb9f` |
| 远端 `main` | `781d90dbb0778dd2d5a2adcf17ddc741d787bb9f`（与本地 HEAD 一致） |
| 追踪文件数 | 25（20 个工具文件 + 5 份交付文档） |
| 提交数 | 10 |

上述字段由 GitHub 公开 API 于 2026-11-21T08:28:32Z 读回，不依赖本地状态：

```bash
curl -s https://api.github.com/repos/zhou96754128/cs146s-c5-repo-czlint-zh
curl -s "https://api.github.com/repos/zhou96754128/cs146s-c5-repo-czlint-zh/git/trees/main?recursive=1"
```

## 2. 仓库里有什么

`czlint` 是一个零依赖的 Git 提交信息规范检查器：15 条可配置规则、一个 0–100 健康分、一行可选 `commit-msg` 钩子。仅用 Python 3.8+ 标准库，无第三方依赖，不需联网。

| 路径 | 内容 |
|---|---|
| `czlint/rules.py` | 15 条规则与解析器（纯函数，无文件 IO） |
| `czlint/config.py` | `.czlintrc.json` 读取与白名单校验 |
| `czlint/gitlog.py` | 唯一调用 `git log` 的模块，异常统一包成 `GitError` |
| `czlint/report.py` | 健康分条与统计渲染 |
| `czlint/cli.py` | 命令行入口与四档退出码契约 |
| `tests/` | 56 项单元测试 |
| `.czlintrc.json` | 本仓库自己的配置（自己检查自己） |
| `README.md` / `CONTRIBUTING.md` / `CHANGELOG.md` | 使用、贡献与变更记录 |
| `.github/` | issue 模板与 PR 模板 |

## 3. 任何人都能验的三条命令

无需安装、无需联网、无需我的机器：

```bash
git clone https://github.com/zhou96754128/cs146s-c5-repo-czlint-zh.git
cd cs146s-c5-repo-czlint-zh

python3 -m unittest discover -s tests -t .   # 期望：Ran 56 tests ... OK
python3 -m czlint --stats                    # 期望：11 条提交，合规 11 条（100.0%），RC=0
printf 'update stuff\n' > /tmp/bad.txt
python3 -m czlint --file /tmp/bad.txt        # 期望：R002 error，RC=1
```

这三条是本仓库的自我验收线：测试覆盖行为、自检证明工具能检查真实历史、最后一条证明它确实会拒绝烂消息而不是永远放行。

## 4. 验收证据的边界

- 本仓库内**不含**日志文件。四项命令的原始输出落在挑战工作目录的 `logs/`（`01_单元测试.txt`、`02_自检历史.txt`、`03_空消息负向.txt`、`04_钩子拦截.txt`），随交付一起提交。
- 仓库的 11 条提交是真实增量历史（脚手架 → 规则 → 配置 → 报告 → CLI → 测试 → 文档 → 交付文档），不是最后一次性灌入。
- 已知限制照实写在 `README.md`「已知限制」一节：只覆盖 commit-msg 层面、宽度按字符数而非终端显示宽度、不提供 `--fix` 自动改写。
