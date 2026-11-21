"""配置层单测。

重点覆盖两类真实事故：
 * 键名拼错被静默忽略（→ 必须抛错，而不是"看起来生效了"）
 * 规则级别写了非法值（→ 必须抛错，否则判定结果不可预期）
"""

import json
import os
import tempfile
import unittest

from czlint.config import Config, ConfigError, apply_dict, load_config
from czlint.rules import RULE_IDS


class ApplyDictTest(unittest.TestCase):
    def test_defaults(self):
        cfg = Config()
        self.assertIn("feat", cfg.types)
        self.assertEqual(cfg.max_subject_length, 72)
        self.assertFalse(cfg.scope_required)

    def test_unknown_key_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            apply_dict(Config(), {"maxSubjectLen": 50}, RULE_IDS)
        self.assertIn("未知配置项", str(ctx.exception))

    def test_invalid_severity_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            apply_dict(Config(), {"rules": {"R003": "fatal"}}, RULE_IDS)
        self.assertIn("严重级别", str(ctx.exception))

    def test_unknown_rule_rejected(self):
        with self.assertRaises(ConfigError):
            apply_dict(Config(), {"rules": {"R999": "warn"}}, RULE_IDS)

    def test_empty_types_rejected(self):
        with self.assertRaises(ConfigError):
            apply_dict(Config(), {"types": []}, RULE_IDS)

    def test_negative_limit_rejected(self):
        with self.assertRaises(ConfigError):
            apply_dict(Config(), {"maxSubjectLength": 0}, RULE_IDS)
        with self.assertRaises(ConfigError):
            apply_dict(Config(), {"maxSubjectLength": True}, RULE_IDS)

    def test_scope_required_must_be_bool(self):
        with self.assertRaises(ConfigError):
            apply_dict(Config(), {"scopeRequired": "yes"}, RULE_IDS)

    def test_override_does_not_mutate_input(self):
        base = Config()
        new = apply_dict(base, {"types": ["feat"]}, RULE_IDS)
        self.assertEqual(new.types, ["feat"])
        self.assertIn("fix", base.types)

    def test_severity_lookup(self):
        cfg = apply_dict(Config(), {"rules": {"R008": "error"}}, RULE_IDS)
        self.assertEqual(cfg.severity("R008", "off"), "error")
        self.assertEqual(cfg.severity("R001", "error"), "error")


class LoadConfigTest(unittest.TestCase):
    def test_reads_default_rc_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".czlintrc.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"scopes": ["api"], "rules": {"R009": "off"}}, fh)
            cfg = load_config(tmp, None, RULE_IDS)
            self.assertEqual(cfg.scopes, ["api"])
            self.assertEqual(cfg.severity("R009", "warn"), "off")
            self.assertEqual(cfg.source, path)

    def test_missing_explicit_config_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                load_config(tmp, os.path.join(tmp, "nope.json"), RULE_IDS)

    def test_broken_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            with self.assertRaises(ConfigError):
                load_config(tmp, path, RULE_IDS)

    def test_explicit_path_wins_over_repo_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            default = os.path.join(tmp, ".czlintrc.json")
            with open(default, "w", encoding="utf-8") as fh:
                json.dump({"maxSubjectLength": 40}, fh)
            explicit = os.path.join(tmp, "other.json")
            with open(explicit, "w", encoding="utf-8") as fh:
                json.dump({"maxSubjectLength": 60}, fh)
            cfg = load_config(tmp, explicit, RULE_IDS)
            self.assertEqual(cfg.max_subject_length, 60)


if __name__ == "__main__":
    unittest.main()
