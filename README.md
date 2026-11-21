# czlint · Git 提交信息规范检查器

零依赖、可离线运行的 commit message linter。**clone 下来就能跑**，不需要 `pip install`、不需要虚拟环境、不访问网络，只要求 `python3 >= 3.8`。

```bash
git clone https://github.com/zhou96754128/cs146s-c5-repo-czlint-zh.git
cd cs146s-c5-repo-czlint-zh
python3 -m czlint --version     # czlint 1.0.0
python3 -m unittest discover -s tests -t .   # Ran 56 tests ... OK
```

## 这个工具解决什么问题

团队推行 Conventional Commits 时最常见的失败不是「大家不知道规范」，而是**检查太晚、反馈太糙**：

- 规范写在 wiki 里，提交时没人看，合进主干才被评审提出来，返工成本高；
- 现成的提交信息检查器通常要装 Node 工具链，CI 上一装就是几分钟，小项目直接放弃；
- 报错只说「invalid commit message」，不说是哪一条规则、哪个字符位置、怎么改。

`czlint` 的取舍是：**用标准库把检查放到 commit-msg 钩子里，毫秒级返回，每条问题都带规则号、行号和修改建议**。

选题不是凭空来的。此前做 C5A 仓库分析时，我在统计真实仓库的 `conventional_ratio` 时发现一个陷阱：同一个仓库按不同历史区间统计，合规率能差出十几个百分点——因为早年还没有约定、或者早期提交是团队迁移仓库时批量导入的。**如果检查器只给一个总数、不给逐条明细，这种时代偏置永远看不出来。** 所以这里第一件事就是把「逐条可定位」作为硬要求：每条问题都有 `R0xx` 规则号 + 行号 + 建议，能直接反推是哪段历史在拖分。

## 四种用法

```bash
# 1) 检查一个消息文件（commit-msg 钩子用的就是这个）
python3 -m czlint --file .git/COMMIT_EDITMSG

# 2) 从管道读（CI 里校验 PR 标题）
echo "feat(cli): 增加 --stats 汇总" | python3 -m czlint --stdin

# 3) 检查一段历史，并输出汇总
python3 -m czlint HEAD~20..HEAD --stats

# 4) 装成当前仓库的 commit-msg 钩子（已存在钩子时拒绝覆盖，退出码 2）
python3 -m czlint --install-hook
```

常用开关：`--repo <路径>` 指定仓库、`--config <文件>` 指定配置、`--json` 输出机器可读结果、`--no-hints` 关掉建议行、`--fail-on-warn` 让警告也失败、`--no-merges` / `--max-count N` 控制检查范围、`--all` 检查全部历史。

### 真实输出（本仓库实测，未经修饰）

配置内有 `rules` scope，这条消息合规：

```
$ python3 -m czlint --file msg_good.txt --stats
检查目标：消息文件 msg_good.txt
当前配置：./.czlintrc.json
[OK  ] WORKTREE fix(rules): 修复空输入导致的崩溃

汇总：1 条提交，合规 1 条（100.0%），error 0 个，warn 0 个，平均健康分 100.0
没有任何规则被触发。
```

同一条消息把 type 写成 `fixed`、scope 写成 `parsr`、标题和正文之间不留空行：

```
$ python3 -m czlint --file msg_bad.txt --stats
[  70] ███████░░░ WORKTREE fixed(parsr): 修复解析器在空输入下崩溃的问题，同时…
        ERROR R003  L1  未知 type 'fixed'
              ↳ 允许的 type：feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
        ERROR R004  L1  未知 scope 'parsr'
              ↳ 允许的 scope：cli, rules, config, report, gitlog, docs, ci, tests
        ERROR R011  L2  标题与正文之间缺少空行
              ↳ git 会把紧贴标题的第二行当作续行，务必空一行

汇总：1 条提交，合规 0 条（0.0%），error 3 个，warn 0 个，平均健康分 70.0
```

健康分算法：`100 - 10 × error - 3 × warn`，下限 0。有问题的提交会显示分数和十格进度条，没问题的只占一行——避免一屏刷满。

## 配置：`.czlintrc.json`

放在仓库根即可被自动发现，也可以用 `--config` 指定绝对路径（显式路径优先）。

```json
{
  "types": ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"],
  "scopes": ["cli", "rules", "config", "report", "gitlog", "docs", "ci", "tests"],
  "scopeRequired": false,
  "maxSubjectLength": 72,
  "maxHeaderWidth": 72,
  "maxBodyLineWidth": 72,
  "strictMerges": false,
  "ignoreSubjects": [],
  "rules": { "R008": "off", "R009": "warn" }
}
```

| 字段 | 作用 | 默认 |
| --- | --- | --- |
| `types` / `scopes` | 允许的 type 与 scope 白名单 | 见上；`scopes` 为空表示不校验 scope |
| `scopeRequired` | 是否强制写 scope | `false` |
| `maxSubjectLength` / `maxHeaderWidth` | subject 长度、整行标题宽度 | `72` / `72` |
| `maxBodyLineWidth` | 正文单行宽度 | `72` |
| `strictMerges` | 是否对 `Merge ...` 也做格式检查 | `false` |
| `ignoreSubjects` | 按标题精确豁免（给依赖升级机器人用） | `[]` |
| `rules` | 逐条规则的严重级别 `off` / `warn` / `error` | 见下方规则表 |

**配置项拼错会直接报错，而不是被静默忽略**：所有 key 走白名单校验，写成了 `maxSubjectLen` 会抛 `ConfigError` 并指出未知项。被静默忽略的配置比没有配置更危险——你会以为它在生效。

## 规则清单

15 条规则，ID 一经发布不再复用（改语义就换新号，避免历史报告对不上号）。

| 规则 | 检查内容 | 默认级别 |
| --- | --- | --- |
| R001 | 提交信息不能为空 | error |
| R002 | 标题必须形如 `type(scope)!: subject` | error |
| R003 | `type` 必须是允许的类型之一 | error |
| R004 | `scope` 必须是允许的范围之一 | error |
| R005 | 本仓库要求显式 scope（`scopeRequired`） | error |
| R006 | `subject` 不能为空 | error |
| R007 | `subject` 长度不得超过上限 | error |
| R008 | `subject` 首字母不应大写 | off |
| R009 | `subject` 不应以句号结尾 | warn |
| R010 | 标题行宽度不得超过上限 | error |
| R011 | 标题与正文之间必须空一行 | error |
| R012 | 正文单行宽度不得超过上限 | warn |
| R013 | 用 `!` 标记破坏性变更时，正文必须给出 `BREAKING CHANGE` 说明 | error |
| R014 | 行尾不应有多余空白 | warn |
| R015 | 正文不应出现连续空行 | warn |

R008 默认关闭是有意的：中文团队里 subject 常以英文小写动词开头，但 `Fix`、`Add` 这类首字母大写的写法在中文语境下并不算错，强行报错只会让人把工具关掉。

`Merge branch ...`、`Merge pull request ...`、`Revert "..."` 这三类由 git 自动生成的消息默认不做格式检查，只做行尾空白检查——机器写出来的消息不应该让人来背锅。把 `strictMerges` 打开可以对 merge 提交也严格校验。

## 退出码契约

脚本化调用靠退出码判断，所以这里的语义是固定的：

| 退出码 | 含义 |
| --- | --- |
| `0` | 没有 error（开了 `--fail-on-warn` 时也没有 warn） |
| `1` | 存在 error（或开了 `--fail-on-warn` 且有 warn） |
| `2` | 用法或配置非法；`--install-hook` 时已存在 commit-msg 钩子 |
| `3` | git 操作失败（不是仓库、范围不存在等） |

为 `--install-hook` 复用 `2` 而不是 `0` 也是有意的：CI 里误调一次装钩子，如果返回 0 会被当成「检查通过」，把真正的失败吞掉。

## 设计决策

**规则是纯函数。** `check_message(message, cfg) -> List[Issue]` 不读文件、不读环境、不跑 git。所以 56 项测试里绝大多数不需要建临时仓库，也不需要 mock——直接传字符串断言规则号。想在 CI 里批量验证历史提交，那是 `gitlog` 层的事，规则层不需要知道。

**判定与展示分离。** `rules.py` 只产出 `Issue` 对象，`report.py` 负责文本/JSON/统计。加一种输出格式不用碰规则代码，改规则也不会把输出格式改坏。

**严重级别走配置，不硬编码。** 同一条规则在不同仓库的容忍度不同：文档仓库可以要求 72 列，一个人维护的小工具仓库不必。把级别写死，用户唯一的出路就是 fork 或者关掉整个检查。

**配置拼错必须报错。** 见上一节：白名单校验 + `ConfigError`。

## 测试

```bash
python3 -m unittest discover -s tests -t .
# ........................................................
# Ran 56 tests in 0.4s
# OK
```

覆盖三层：`test_rules.py` 逐条规则的正反例（含「不该报的不能报」的负向断言）、`test_config.py` 的默认值/覆盖/白名单拒绝、`test_cli.py` 的退出码契约与钩子安装。

## 目录结构

```
czlint/
  __init__.py     版本号
  __main__.py     python3 -m czlint 入口（钩子依赖它）
  config.py       配置加载与白名单校验
  rules.py        15 条规则 + 解析 + 评分（纯函数）
  gitlog.py       从 git 读提交（唯一会调外部命令的模块）
  report.py       文本 / 统计渲染
  cli.py          参数解析、退出码、钩子安装
tests/            56 项单元测试
.czlintrc.json    本仓库自己的配置
CONTRIBUTING.md   贡献方式与提交约定
CHANGELOG.md      版本记录
```

## 已知限制

- 只检查提交信息，不检查 diff 内容、不强制「一提交只做一件事」——那需要语义理解，超出静态规则能做到的范围。
- 宽度按字符数算，不按终端显示宽度算：中文字符在多数终端占 2 列，所以含中文的长标题在终端里看起来会比 72 更宽。
- 不做自动修复（`--fix`）。提交信息改写涉及 amend / rebase，工具不该替人做这种不可逆操作。

## License

[MIT](LICENSE) © 2026 Zhouruoying

