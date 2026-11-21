# 参与贡献

感谢你愿意改进 `czlint`。这是一个刻意保持「零依赖、纯标准库」的小工具，所以下面的约定都围绕一件事：**别为了功能把门槛抬高**。

## 快速开始

```bash
git clone https://github.com/zhou96754128/cs146s-c5-repo-czlint-zh.git
cd cs146s-c5-repo-czlint-zh
python3 -m unittest discover -s tests -t .
```

不需要 `pip install`，不需要虚拟环境。如果你的改动需要新增依赖才能测试，那这个改动本身就值得重新讨论。

## 提交信息约定

本仓库用 `czlint` 检查自己的提交信息，所以请先把它装成钩子：

```bash
python3 -m czlint --install-hook
```

格式：`type(scope): subject`

- `type` 取 `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`
- `scope` 建议写，取值见 `.czlintrc.json`；改不到对应 scope 时请先讨论要不要扩白名单
- subject 用中文或英文都行，不加句号，不超过 72 字符
- 标题和正文之间空一行
- 破坏性变更在 type 后加 `!`，并在正文用 `BREAKING CHANGE:` 说明影响面

## 提交流程

1. 从 `main` 切出分支：`git switch -c feat/cli-json-output`
2. 改动 + 补测试，跑 `python3 -m unittest discover -s tests -t .` 确认全绿
3. 提交（钩子会自动校验提交信息）
4. 开 PR，用关联关键词（`Closes #12`）指向对应 issue

PR 描述请填「改了什么 / 为什么 / 怎么验证的」三件事。只写「优化代码」的 PR 会被要求补充。

## 新增一条规则

规则是本项目最需要节制的部分——每加一条，就多一个让使用者关掉整个工具的理由。新增前请在 issue 里说明：

- 这条规则在真实仓库里造成过什么问题？有没有具体提交例子？
- 为什么现有 15 条覆盖不了它？
- 默认级别应该是 `error`、`warn` 还是 `off`？

实现要求：

- 在 `rules.py` 里写纯函数式判定，**不读文件、不读环境、不调 git**
- 规则 ID 顺延，**不要复用已发布的 ID**：语义变了就换新号，否则历史报告会对不上号
- 在 `RULE_TITLES` 里加中文标题，`message` 说清「哪里错了」，`hint` 说清「怎么改」
- 在 `tests/test_rules.py` 里补正例和**反例**——「不该报的不能报」和「该报的必须报」同样重要

## 修改已有规则

改变判定语义 = 破坏性变更。请在 PR 里写明：受影响的仓库类型、历史报告里会新增/消失哪些问题、是否需要给使用者一个过渡期（先把默认级别降为 `warn`）。

## 报告问题

用 issue 模板，附上：

- `python3 -m czlint --version` 的输出
- 触发问题的完整提交信息（可脱敏）
- 期望结果与实际结果

能贴成一段可复制的命令最好：

```bash
echo "feat(cli): xxx" | python3 -m czlint --stdin
```

## 版本策略

语义化版本。规则语义变更、退出码变更算 breaking，升 major；新增规则默认 `off` 算 minor；修 bug 算 patch。每次发版更新 `CHANGELOG.md`。
