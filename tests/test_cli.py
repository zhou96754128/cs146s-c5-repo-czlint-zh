"""CLI 单测：用真实临时 git 仓库跑，断言退出码而不是断言文字。

退出码是契约（0 通过 / 1 有 error / 2 用法或配置错 / 3 git 失败），
钩子和 CI 都依赖它，所以这里专门锁住。
"""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest

from czlint.cli import EXIT_GIT, EXIT_LINT, EXIT_OK, EXIT_USAGE, main


def run(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def git(repo, *args):
    cmd = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"] + list(args)
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("git %s 失败：%s" % (" ".join(args), proc.stderr))
    return proc.stdout


class MessageFileTest(unittest.TestCase):
    def test_good_message_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "msg.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("fix(parser): 修复空指针解引用\n\n补了回归用例。\n")
            code, out, _ = run(["--file", path])
            self.assertEqual(code, EXIT_OK)
            self.assertIn("[OK  ]", out)

    def test_bad_message_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "msg.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("update stuff\n")
            code, out, _ = run(["--file", path])
            self.assertEqual(code, EXIT_LINT)
            self.assertIn("R002", out)

    def test_comment_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "msg.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("fix: 修复超时\n\n# 这是 git 的注释行\n")
            code, _, _ = run(["--file", path])
            self.assertEqual(code, EXIT_OK)

    def test_missing_message_file_is_usage_error(self):
        code, _, err = run(["--file", "/nonexistent/msg.txt"])
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn("读取消息失败", err)

    def test_fail_on_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "msg.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("fix: 修复超时.\n")
            self.assertEqual(run(["--file", path])[0], EXIT_OK)
            self.assertEqual(run(["--file", path, "--fail-on-warn"])[0], EXIT_LINT)


class ConfigErrorTest(unittest.TestCase):
    def test_unknown_key_exits_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"maxSubjectLen": 40}, fh)
            code, _, err = run(["--config", path, "--stdin"])
            self.assertEqual(code, EXIT_USAGE)
            self.assertIn("未知配置项", err)


class GitRepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git(self.repo, "init", "-q")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "chore: 初始化仓库")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "update stuff")

    def tearDown(self):
        self.tmp.cleanup()

    def test_checks_range(self):
        code, out, _ = run(["--repo", self.repo, "HEAD~1..HEAD"])
        self.assertEqual(code, EXIT_LINT)
        self.assertIn("R002", out)

    def test_all_history(self):
        code, out, _ = run(["--repo", self.repo, "--all"])
        self.assertEqual(code, EXIT_LINT)
        self.assertIn("chore: 初始化仓库", out)

    def test_json_output_is_parseable(self):
        code, out, _ = run(["--repo", self.repo, "--all", "--json"])
        data = json.loads(out)
        self.assertEqual(data["summary"]["commits"], 2)
        self.assertEqual(code, EXIT_LINT)
        self.assertIn("issues", data["commits"][0])

    def test_stats_section(self):
        code, out, _ = run(["--repo", self.repo, "--all", "--stats"])
        self.assertIn("问题分布", out)

    def test_non_repo_is_git_error(self):
        with tempfile.TemporaryDirectory() as plain:
            code, _, err = run(["--repo", plain, "--all"])
            self.assertEqual(code, EXIT_GIT)
            self.assertIn("读取 git 失败", err)

    def test_install_hook(self):
        code, out, _ = run(["--repo", self.repo, "--install-hook"])
        self.assertEqual(code, EXIT_OK)
        hook = os.path.join(self.repo, ".git", "hooks", "commit-msg")
        self.assertTrue(os.path.isfile(hook))
        self.assertTrue(os.access(hook, os.X_OK))
        # 第二次安装不得覆盖已有钩子
        code2, _, _ = run(["--repo", self.repo, "--install-hook"])
        self.assertEqual(code2, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
