"""规则层单测：每条规则至少一个正例和一个反例。

规则是纯函数，因此这些测试不需要 git 仓库、不需要临时文件，
在任意机器上 `python3 -m unittest` 就能跑。
"""

import unittest

from czlint.config import Config
from czlint.rules import RULE_IDS, check_message, parse, score


def ids(issues):
    return [i.rule_id for i in issues]


class ParseTest(unittest.TestCase):
    def test_full_header(self):
        p = parse("feat(api)!: 支持批量导入\n\nBREAKING CHANGE: 去掉旧字段")
        self.assertEqual(p.type, "feat")
        self.assertEqual(p.scope, "api")
        self.assertTrue(p.breaking)
        self.assertEqual(p.subject, "支持批量导入")
        self.assertTrue(p.blank_after_header)
        self.assertEqual(p.body_lines, ["BREAKING CHANGE: 去掉旧字段"])

    def test_body_without_blank_line(self):
        p = parse("fix: 修复超时\n正文紧贴标题")
        self.assertFalse(p.blank_after_header)
        self.assertEqual(p.body_lines, ["正文紧贴标题"])

    def test_crlf_is_normalized(self):
        p = parse("fix: 修复\r\n\r\n正文\r\n")
        self.assertEqual(p.subject, "修复")
        self.assertEqual(p.body_lines, ["正文"])

    def test_merge_detected(self):
        self.assertTrue(parse("Merge branch 'dev' into main").is_merge)
        self.assertTrue(parse('Revert "feat: 加功能"').is_revert)


class RuleTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_valid_message_is_clean(self):
        self.assertEqual(check_message("fix(parser): 修复空指针解引用", self.cfg), [])

    def test_r001_empty(self):
        self.assertEqual(ids(check_message("   \n ", self.cfg)), ["R001"])

    def test_r002_unparseable(self):
        self.assertIn("R002", ids(check_message("update some stuff", self.cfg)))

    def test_r003_unknown_type(self):
        self.assertIn("R003", ids(check_message("wip: 临时提交", self.cfg)))

    def test_r004_unknown_scope(self):
        cfg = Config(scopes=["api", "cli"])
        self.assertIn("R004", ids(check_message("fix(db): 修连接池", cfg)))

    def test_r004_ignored_when_scopes_empty(self):
        self.assertNotIn("R004", ids(check_message("fix(db): 修连接池", self.cfg)))

    def test_r005_scope_required(self):
        cfg = Config(scope_required=True)
        self.assertIn("R005", ids(check_message("fix: 修复", cfg)))

    def test_r006_empty_subject(self):
        self.assertIn("R006", ids(check_message("fix: ", self.cfg)))

    def test_r007_subject_too_long(self):
        cfg = Config(max_subject_length=10)
        self.assertIn("R007", ids(check_message("fix: " + "改" * 11, cfg)))

    def test_r008_off_by_default(self):
        self.assertNotIn("R008", ids(check_message("fix: Fix cursor", self.cfg)))

    def test_r008_when_turned_on(self):
        cfg = Config(rules={"R008": "error"})
        self.assertIn("R008", ids(check_message("fix: Fix cursor", cfg)))

    def test_r009_trailing_period(self):
        self.assertIn("R009", ids(check_message("fix: 修复登录失败.", self.cfg)))
        self.assertIn("R009", ids(check_message("fix: 修复登录失败。", self.cfg)))

    def test_r010_header_too_wide(self):
        cfg = Config(max_header_width=20)
        self.assertIn("R010", ids(check_message("fix(cli): 一个很长的标题用来撑宽", cfg)))

    def test_r011_missing_blank_line(self):
        self.assertIn("R011", ids(check_message("fix: 修复\n正文紧贴标题", self.cfg)))
        self.assertNotIn("R011", ids(check_message("fix: 修复\n\n正文另起一段", self.cfg)))

    def test_r012_body_line_too_wide(self):
        cfg = Config(max_body_line_width=10)
        self.assertIn("R012", ids(check_message("fix: 修复\n\n" + "这是一段很长的正文内容用来触发宽度检查", cfg)))

    def test_r013_breaking_without_footer(self):
        self.assertIn("R013", ids(check_message("feat!: 重写配置格式", self.cfg)))

    def test_r013_satisfied_by_footer(self):
        msg = "feat!: 重写配置格式\n\nBREAKING CHANGE: 老配置需要迁移"
        self.assertNotIn("R013", ids(check_message(msg, self.cfg)))

    def test_r014_trailing_whitespace(self):
        self.assertIn("R014", ids(check_message("fix: 修复  \n\n正文", self.cfg)))

    def test_r015_consecutive_blank_lines(self):
        self.assertIn("R015", ids(check_message("fix: 修复\n\n第一段\n\n\n第二段", self.cfg)))

    def test_merge_skipped_by_default(self):
        self.assertEqual(check_message("Merge branch 'dev' into main", self.cfg), [])

    def test_merge_checked_when_strict(self):
        cfg = Config(strict_merges=True)
        self.assertIn("R002", ids(check_message("Merge branch 'dev' into main", cfg)))

    def test_ignore_subject(self):
        cfg = Config(ignore_subjects=["Bump deps"])
        self.assertEqual(check_message("Bump deps", cfg), [])


class ScoreTest(unittest.TestCase):
    def test_perfect_score(self):
        self.assertEqual(score([]), 100)

    def test_error_deduction(self):
        issues = check_message("update stuff", Config())
        self.assertEqual(score(issues), 90)

    def test_floor_at_zero(self):
        issues = check_message("x", Config())
        self.assertEqual(score(issues * 20), 0)


class RuleRegistryTest(unittest.TestCase):
    def test_rule_ids_unique(self):
        self.assertEqual(len(RULE_IDS), len(set(RULE_IDS)))

    def test_rule_ids_stable(self):
        self.assertEqual(RULE_IDS, ["R%03d" % n for n in range(1, 16)])


if __name__ == "__main__":
    unittest.main()
