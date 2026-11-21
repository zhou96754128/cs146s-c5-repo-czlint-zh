---
name: 报告问题
about: 检查结果不符合预期、误报或漏报
title: "[bug] "
labels: bug
---

## 现象

<!-- 一句话说清：什么提交信息、什么配置，得到什么结果 -->

## 复现方式

```bash
# 请尽量给成一段可直接粘贴执行的命令
echo "feat(cli): xxx" | python3 -m czlint --stdin
```

## 期望结果

<!-- 你预期通过还是报错？期望命中哪条规则？ -->

## 实际结果

```
把终端输出粘在这里
```

## 环境

- `python3 -m czlint --version`：
- `python3 --version`：
- 操作系统：
- 是否使用自定义 `.czlintrc.json`：是 / 否（是的话请贴出）

## 是误报还是漏报

- [ ] 误报：本该通过却报了 error / warn
- [ ] 漏报：明显不合规却没报
- [ ] 崩溃或异常退出
