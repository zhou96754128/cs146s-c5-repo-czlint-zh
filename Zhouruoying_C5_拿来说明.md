# C5 拿来说明：czlint 怎么被别人拿走去用

这份说明面向「想在自己项目里管住提交信息」的人，不面向评审。它只回答四件事：**该不该拿、怎么拿、怎么用、坑在哪**。

## 一、什么情况下该拿走

三条里中任意一条，就值得拿：

1. 团队里 `git log` 已经没法看了——一半是「update」「fix」「修改」，回溯问题时只能靠猜。
2. 有 CI，但提交质量没人管；想在不引入 Node 生态、不装任何依赖的前提下加一道门。
3. 你自己写规范文档，但没人遵守——规范写在 wiki 里没有执行力，写进钩子才有。

什么情况下不必拿：团队已经在用 commitizen / commitlint 且运转良好；或者项目是单人短期脚本，历史无人回溯。这时加工具的维护成本高于收益。

## 二、怎么拿（三种拿走方式，按侵入性从低到高）

### 方式 A：完全不装，先看它怎么说

```bash
git clone https://github.com/zhou96754128/cs146s-c5-repo-czlint-zh.git /tmp/czlint
cd /tmp/czlint
python3 -m czlint --repo /your/project --stats
```

注意 `cd /tmp/czlint` 这一步不能省：czlint 是包，必须用 `-m` 在包所在目录里跑。写成 `python3 /tmp/czlint/czlint` 会因顶层包导不进来而静默退出 1（我自己第一版文档就写错了，交付前实测才发现）。

零安装、零改动、不动你的仓库。先看「11 条提交里有几条不合规、平均健康分多少」，觉得有用再往下走。这一步是我建议所有人的第一步——先拿报告，再决定要不要装。

### 方式 B：把 `czlint/` 目录拷进项目（推荐）

```bash
cp -R /tmp/czlint/czlint ./czlint
cp /tmp/czlint/.czlintrc.json ./.czlintrc.json
```

没有依赖，没有 `pip install`，没有 `node_modules`。拷完即可 `python3 -m czlint --stats`。

代价是这份代码进了你的仓库，要跟着你的代码一起被 review。如果不想这样，用方式 C。

### 方式 C：只在自己的 git 钩子里引用（不进项目仓库）

```bash
cd /tmp/czlint
python3 -m czlint --install-hook --repo /your/project
```

钩子内容是一行 `exec python3 -m czlint --file "$1"`，**但这条路要求 `czlint` 在 `PYTHONPATH` 里**。更稳的做法是拷一份到 `~/.local/share/czlint`，钩子里写绝对路径：

```bash
cp -R /tmp/czlint/czlint ~/.local/share/czlint/czlint
printf '#!/bin/sh\nexec python3 -m czlint --file "$1" --config %s/.czlintrc.json\n' "$HOME/.local/share/czlint" > .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

这是我推荐给「只想管自己的提交、不想动团队仓库」的人的形态：工具在你机器上，项目仓库里一行代码都不多。

## 三、怎么配

拷一份 `.czlintrc.json` 到项目根，按团队习惯改：

```json
{
  "types": ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"],
  "scopes": ["api", "web", "db", "docs", "ci"],
  "scopeRequired": true,
  "maxSubjectLength": 60,
  "rules": { "R008": "off", "R009": "warn", "R012": "off" }
}
```

改配置时只需要知道三件事：

- **`scopes` 是白名单，必须是封闭集合**。写成 `[]` 或干脆不写 `scopes` 则 R004 全部不触发。团队 scope 一开始会打架，建议先不要开 `scopeRequired`，跑一周再说。
- **每个规则可单独设 `off` / `warn` / `error`**。`warn` 只扣分不失败，是「先提醒、后强制」的过渡态，我给所有中文字宽类规则（R010/R012）默认都是 `warn`，因为有中文时宽度判定偏松。
- **字段名拼错会直接报错**，不会静默忽略。这是刻意设计的——配置被忽略是最贵的失败，使用者会以为它在保护自己。

## 四、放进 CI

```yaml
# .github/workflows/commit-lint.yml
name: commit-lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }     # 必须完整历史，浅克隆没法体检
      - run: python3 -m czlint "${{ github.event.pull_request.base.sha }}..HEAD" --stats
```

两个必须知道的点：

1. **`fetch-depth: 0`**。浅克隆只有一条提交，`--stats` 等于什么都没查。我自己第一次就踩了这个坑。
2. **用 `--stats` 拿退出码，别只看输出**。0 = 合规，1 = 有 error，2 = 配置写错，3 = git 调用失败。CI 里把 1 和 2 当同一件事处理，就会逼着开发者用 `--no-verify` 绕过——那就等于把门拆了。

## 五、已知坑（都是我实际踩过的）

| 坑 | 现象 | 处理 |
|---|---|---|
| `fetch-depth` 默认 1 | `--stats` 只统计 1 条提交 | workflow 里设 `fetch-depth: 0` |
| 中文按字符计宽 | 中文标题 30 字被算作 30 宽度，实际显示约 60 列 | 宽度类规则默认 `warn`，或在 `.czlintrc.json` 调大 `maxHeaderWidth` |
| merge 提交被拦 | 自动生成的 `Merge branch 'x'` 报错 | 默认对 merge/revert 只查行尾空白；仍被拦时用 `strictMerges: false`（默认值） |
| 钩子已存在 | `--install-hook` 返回 2 | 不覆盖是刻意设计：避免冲掉 husky 之类已有钩子。先备份再手动替换 |
| `python3 -m czlint` 无输出退出 1 | 缺 `__main__.py` 时的静默失败 | 1.0.0 已修复；若你拷的是旧版，检查 `czlint/__main__.py` 是否存在 |
| 提交信息里带 `!` | 报 R013 要求正文说明破坏性变更 | 这是想要的：`feat(api)!: ...` 必须在正文写 `BREAKING CHANGE:`，否则等于没告诉调用方 |

## 六、它不做什么（别指望）

- 不判断提交内容与 subject 是否相符——那是人的问题，工具判不了。
- 不做 `--fix` 自动改写。自动改提交信息风险大于收益，留作后续「建议 + 人工确认」。
- 不做跨提交的重复检测（同一条消息反复用，本工具不管）。
- 不做 i18n，输出中文。
- 不读 merge 的双亲，只做格式检查，不做合并策略检查。

## 七、验收标准（你怎么判断它真的在你项目里生效了）

三步，任一步失败就是没生效：

```bash
# 1) 工具本身能跑
python3 -m czlint --version                    # → czlint 1.0.0

# 2) 能读你的历史
python3 -m czlint --stats                      # → 有汇总行，RC 为 0 或 1

# 3) 钩子真的拦得住
printf 'update stuff\n' > /tmp/bad.txt
python3 -m czlint --file /tmp/bad.txt ; echo "RC=$?"   # → RC=1，且输出含 R002
```

第 3 步是最容易被跳过也最该做的一步：钩子「装上」和「拦得住」是两件事，我自己就踩过装上了但永远不会执行的坑。真实提交一次烂消息，被拒了，才算装好。
