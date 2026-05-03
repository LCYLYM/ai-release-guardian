from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from ai_release_guardian.guardian import Severity, main, scan_path


FIXTURES = Path(__file__).parent / "fixtures"


class GuardianTests(unittest.TestCase):
    def test_safe_fixture_has_no_findings(self) -> None:
        result = scan_path(FIXTURES / "safe")
        self.assertEqual([], result.findings)
        self.assertFalse(result.has_failures(Severity.HIGH))

    def test_risky_fixture_finds_ai_context_source_map_env_and_mcp(self) -> None:
        result = scan_path(FIXTURES / "risky")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn("ai-context-file", rule_ids)
        self.assertIn("debug-source-map", rule_ids)
        self.assertIn("secret-file", rule_ids)
        self.assertIn("mcp-config", rule_ids)
        self.assertTrue(result.has_failures(Severity.HIGH))

    def test_allowlist_requires_explicit_rule_path_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            allowlist = Path(tmpdir) / "allowlist.json"
            allowlist.write_text(
                json.dumps([
                    {
                        "rule_id": "ai-context-file",
                        "path": "CLAUDE.md",
                        "reason": "synthetic fixture used to test allowlist behavior",
                    }
                ]),
                encoding="utf-8",
            )
            result = scan_path(FIXTURES / "risky", allowlist)
            self.assertNotIn("CLAUDE.md", {finding.path for finding in result.findings})
            self.assertTrue(result.findings)

    def test_zip_and_tar_archives_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            zip_path = tmp / "artifact.zip"
            tar_path = tmp / "artifact.tar.gz"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("bundle/app.js.map", '{"sourcesContent":["secret source"]}')
            with tarfile.open(tar_path, "w:gz") as archive:
                source = FIXTURES / "risky" / "CLAUDE.md"
                archive.add(source, arcname="release/CLAUDE.md")

            zip_rules = {finding.rule_id for finding in scan_path(zip_path).findings}
            tar_rules = {finding.rule_id for finding in scan_path(tar_path).findings}
            self.assertIn("debug-source-map", zip_rules)
            self.assertIn("ai-context-file", tar_rules)

    def test_npm_pack_json_file_list_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_json = Path(tmpdir) / "pack.json"
            pack_json.write_text(
                json.dumps([
                    {
                        "id": "pkg@1.0.0",
                        "files": [
                            {"path": "dist/cli.js"},
                            {"path": "dist/cli.js.map"},
                            {"path": ".mcp.json"},
                        ],
                    }
                ]),
                encoding="utf-8",
            )
            rule_ids = {finding.rule_id for finding in scan_path(pack_json).findings}
            self.assertIn("debug-source-map", rule_ids)
            self.assertIn("mcp-config", rule_ids)

    def test_cli_returns_failure_for_high_findings(self) -> None:
        exit_code = main(["scan", str(FIXTURES / "risky"), "--format", "json"])
        self.assertEqual(1, exit_code)

    def test_cli_returns_success_for_safe_fixture(self) -> None:
        exit_code = main(["scan", str(FIXTURES / "safe")])
        self.assertEqual(0, exit_code)


if __name__ == "__main__":
    unittest.main()
