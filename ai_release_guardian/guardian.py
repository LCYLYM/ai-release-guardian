"""Artifact-level release scanner for AI-era leaks.

The scanner intentionally uses only the Python standard library. It scans the
artifact that is about to ship, not the developer workspace by assumption.
"""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import json
import os
import re
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Iterable, Iterator, Sequence


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_text(cls, value: str) -> "Severity":
        normalized = value.strip().lower()
        mapping = {
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "high": cls.HIGH,
            "critical": cls.CRITICAL,
        }
        if normalized not in mapping:
            raise ValueError(f"unknown severity: {value}")
        return mapping[normalized]

    def to_text(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    reason: str
    recommendation: str
    path_patterns: tuple[str, ...] = ()
    content_patterns: tuple[re.Pattern[str], ...] = ()
    scan_content: bool = True


@dataclass(frozen=True)
class ArtifactEntry:
    path: str
    content: bytes | None = None
    source: str = "filesystem"


@dataclass(frozen=True)
class Finding:
    path: str
    rule_id: str
    severity: Severity
    reason: str
    recommendation: str
    source: str
    evidence: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path,
            "rule_id": self.rule_id,
            "severity": self.severity.to_text(),
            "reason": self.reason,
            "recommendation": self.recommendation,
            "source": self.source,
        }
        if self.evidence:
            payload["evidence"] = self.evidence
        return payload


@dataclass(frozen=True)
class AllowlistEntry:
    rule_id: str
    path: str
    reason: str


@dataclass
class ScanResult:
    target: str
    findings: list[Finding] = field(default_factory=list)
    scanned_entries: int = 0
    skipped_entries: int = 0

    def has_failures(self, threshold: Severity) -> bool:
        return any(finding.severity >= threshold for finding in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "scanned_entries": self.scanned_entries,
            "skipped_entries": self.skipped_entries,
            "findings": [finding.to_dict() for finding in self.findings],
        }


TEXT_BYTES_LIMIT = 2_000_000


RULES: tuple[Rule, ...] = (
    Rule(
        "ai-context-file",
        Severity.HIGH,
        "AI agent context files can expose architecture, workflow, internal endpoints, and safety assumptions.",
        "Remove AI context files from release artifacts; keep local variants outside packaged output.",
        (
            "CLAUDE.md",
            "CLAUDE.local.md",
            "AGENTS.md",
            ".claude/**",
            ".cursor/**",
            ".windsurf/**",
            ".github/copilot-instructions.md",
            "*.prompt.*",
            "*prompt-manifest*",
        ),
    ),
    Rule(
        "mcp-config",
        Severity.HIGH,
        "MCP configuration can expose local servers, tool permissions, environment variable names, or inline credentials.",
        "Keep MCP configuration out of shipped artifacts unless it is a sanitized sample.",
        (".mcp.json", "**/.mcp.json", "*mcp*.json", "*mcp*.toml", "*mcp*.yaml", "*mcp*.yml"),
    ),
    Rule(
        "debug-source-map",
        Severity.HIGH,
        "Source maps and debug symbols can reconstruct private source, prompts, guardrails, and tool-call boundaries.",
        "Do not ship public source maps; upload them to a restricted error tracking service if needed.",
        ("*.map", "*.dSYM", "*.dSYM/**"),
    ),
    Rule(
        "secret-file",
        Severity.CRITICAL,
        "Credential files should never be part of a public release artifact.",
        "Remove the file, rotate exposed credentials, and use environment variables or a secret manager.",
        (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.mobileprovision"),
    ),
    Rule(
        "chat-or-memory-log",
        Severity.HIGH,
        "AI memory, chat transcripts, and tool logs can contain private prompts, code, credentials, or customer data.",
        "Exclude AI runtime logs and memory caches from release packages.",
        ("*chat*transcript*", "*conversation*export*", "*memory*cache*", "*tool*log*", "*.chat.jsonl", "*.messages.jsonl"),
    ),
    Rule(
        "private-key-material",
        Severity.CRITICAL,
        "Private key material was detected in file content.",
        "Remove the key, rotate it immediately, and investigate downstream access.",
        content_patterns=(re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),),
    ),
    Rule(
        "token-like-secret",
        Severity.CRITICAL,
        "Token-like secret material was detected in file content.",
        "Remove the secret, rotate it immediately, and replace it with an environment variable reference.",
        content_patterns=(
            re.compile(r"(?i)(api[_-]?key|secret|token|password|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
        ),
    ),
    Rule(
        "source-map-pointer",
        Severity.HIGH,
        "A sourceMappingURL pointer can expose source maps even when the .map file is not bundled.",
        "Remove public sourceMappingURL comments from production bundles or point them to restricted storage.",
        content_patterns=(re.compile(r"sourceMappingURL\s*="),),
    ),
    Rule(
        "source-map-content",
        Severity.HIGH,
        "sourcesContent embeds original source directly inside a source map.",
        "Generate production source maps without sourcesContent or keep them private.",
        content_patterns=(re.compile(r'"sourcesContent"\s*:'),),
    ),
    Rule(
        "internal-trace",
        Severity.MEDIUM,
        "Internal trace markers can leak project management systems, debug mode, or unreleased feature flags.",
        "Remove internal trace markers or keep them in private diagnostic builds.",
        content_patterns=(
            re.compile(r"\brdar://\d+", re.IGNORECASE),
            re.compile(r"\bJIRA[-_/ ][A-Z]+-\d+\b", re.IGNORECASE),
            re.compile(r"\bDEV_BUILD\b|\bDEBUG\b|\bJUNO_ENABLED\b", re.IGNORECASE),
        ),
    ),
    Rule(
        "ai-data-share-risk",
        Severity.HIGH,
        "AI data or model sharing credentials can expose training data, logs, or writable buckets.",
        "Use scoped, read-only, short-lived URLs and verify storage boundaries before publishing.",
        content_patterns=(
            re.compile(r"(?i)\bSharedAccessSignature\b|\bsig=[A-Za-z0-9%_-]{20,}"),
            re.compile(r"(?i)\btraining[_-]?data\b.*\bhttps?://"),
            re.compile(r"(?i)\bmodel[_-]?(weights|checkpoint)\b.*\bhttps?://"),
        ),
    ),
)


def normalize_artifact_path(path: str) -> str:
    value = path.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def path_matches(pattern: str, path: str) -> bool:
    normalized = normalize_artifact_path(path)
    pattern = pattern.replace("\\", "/").strip("/")
    basename = normalized.rsplit("/", 1)[-1]
    if fnmatch.fnmatchcase(normalized, pattern) or fnmatch.fnmatchcase(basename, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatchcase(normalized, pattern[3:]):
        return True
    if "/**" in pattern:
        prefix = pattern.split("/**", 1)[0]
        return normalized == prefix or normalized.startswith(prefix + "/") or ("/" + prefix + "/") in ("/" + normalized)
    return False


def is_likely_text(content: bytes) -> bool:
    if b"\x00" in content[:4096]:
        return False
    return True


def decode_text(content: bytes) -> str | None:
    sample = content[:TEXT_BYTES_LIMIT]
    if not is_likely_text(sample):
        return None
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return sample.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def iter_directory(path: Path) -> Iterator[ArtifactEntry]:
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [name for name in dirnames if name not in {".git", "__pycache__", ".pytest_cache"}]
        for filename in filenames:
            file_path = Path(root) / filename
            relative = file_path.relative_to(path).as_posix()
            try:
                content = file_path.read_bytes()
            except OSError:
                yield ArtifactEntry(relative, None, "filesystem-unreadable")
                continue
            yield ArtifactEntry(relative, content, "filesystem")


def iter_zip(path: Path) -> Iterator[ArtifactEntry]:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            try:
                content = archive.read(info)
            except (OSError, zipfile.BadZipFile):
                yield ArtifactEntry(info.filename, None, "zip-unreadable")
                continue
            yield ArtifactEntry(info.filename, content, "zip")


def iter_tar(path: Path) -> Iterator[ArtifactEntry]:
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                yield ArtifactEntry(member.name, None, "tar-unreadable")
                continue
            try:
                content = extracted.read()
            except OSError:
                yield ArtifactEntry(member.name, None, "tar-unreadable")
                continue
            yield ArtifactEntry(member.name, content, "tar")


def iter_gzip(path: Path) -> Iterator[ArtifactEntry]:
    output_name = path.name[:-3] if path.name.endswith(".gz") else path.name + ".out"
    with gzip.open(path, "rb") as stream:
        yield ArtifactEntry(output_name, stream.read(), "gzip")


def iter_npm_pack_json(path: Path) -> Iterator[ArtifactEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    packages = data if isinstance(data, list) else [data]
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            continue
        files = package.get("files", [])
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, dict):
                continue
            name = item.get("path") or item.get("name")
            if isinstance(name, str):
                yield ArtifactEntry(name, None, f"npm-pack-json:{index}")


def iter_entries(target: Path) -> Iterator[ArtifactEntry]:
    if target.is_dir():
        yield from iter_directory(target)
        return
    suffixes = [suffix.lower() for suffix in target.suffixes]
    if target.suffix.lower() == ".zip":
        yield from iter_zip(target)
    elif any(suffix in suffixes for suffix in (".tar", ".tgz")) or target.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        yield from iter_tar(target)
    elif target.suffix.lower() == ".gz":
        yield from iter_gzip(target)
    elif target.suffix.lower() == ".json":
        try:
            entries = list(iter_npm_pack_json(target))
        except (json.JSONDecodeError, OSError):
            entries = []
        if entries:
            yield from entries
        else:
            yield ArtifactEntry(target.name, target.read_bytes(), "file")
    else:
        yield ArtifactEntry(target.name, target.read_bytes(), "file")


def load_allowlist(path: Path | None) -> list[AllowlistEntry]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("allowlist must be a JSON array")
    entries: list[AllowlistEntry] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"allowlist entry {index} must be an object")
        rule_id = item.get("rule_id")
        entry_path = item.get("path")
        reason = item.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (rule_id, entry_path, reason)):
            raise ValueError(f"allowlist entry {index} requires non-empty rule_id, path, and reason")
        entries.append(AllowlistEntry(rule_id.strip(), entry_path.strip(), reason.strip()))
    return entries


def is_allowed(finding: Finding, allowlist: Sequence[AllowlistEntry]) -> bool:
    return any(
        entry.rule_id == finding.rule_id and path_matches(entry.path, finding.path)
        for entry in allowlist
    )


def scan_entry(entry: ArtifactEntry) -> list[Finding]:
    findings: list[Finding] = []
    path = normalize_artifact_path(entry.path)
    for rule in RULES:
        for pattern in rule.path_patterns:
            if path_matches(pattern, path):
                findings.append(
                    Finding(
                        path=path,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        reason=rule.reason,
                        recommendation=rule.recommendation,
                        source=entry.source,
                        evidence=f"path matched {pattern}",
                    )
                )
                break
        if entry.content is None or not rule.content_patterns or not rule.scan_content:
            continue
        text = decode_text(entry.content)
        if text is None:
            continue
        for pattern in rule.content_patterns:
            if pattern.search(text):
                findings.append(
                    Finding(
                        path=path,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        reason=rule.reason,
                        recommendation=rule.recommendation,
                        source=entry.source,
                        evidence=f"content matched {pattern.pattern[:80]}",
                    )
                )
                break
    return findings


def scan_path(target: Path | str, allowlist_path: Path | str | None = None) -> ScanResult:
    target_path = Path(target)
    if not target_path.exists():
        raise FileNotFoundError(f"target does not exist: {target_path}")
    allowlist = load_allowlist(Path(allowlist_path) if allowlist_path else None)
    result = ScanResult(target=str(target_path))
    for entry in iter_entries(target_path):
        result.scanned_entries += 1
        entry_findings = [finding for finding in scan_entry(entry) if not is_allowed(finding, allowlist)]
        result.findings.extend(entry_findings)
        if entry.content is None:
            result.skipped_entries += 1
    result.findings.sort(key=lambda finding: (-finding.severity, finding.path, finding.rule_id))
    return result


def render_text(result: ScanResult) -> str:
    lines = [
        f"AI Release Guardian scan: {result.target}",
        f"Scanned entries: {result.scanned_entries}",
        f"Findings: {len(result.findings)}",
    ]
    if result.skipped_entries:
        lines.append(f"Skipped unreadable/contentless entries: {result.skipped_entries}")
    if not result.findings:
        lines.append("No release-blocking AI artifact leaks detected.")
        return "\n".join(lines)
    for finding in result.findings:
        lines.extend(
            [
                "",
                f"[{finding.severity.to_text()}] {finding.rule_id} in {finding.path}",
                f"Reason: {finding.reason}",
                f"Fix: {finding.recommendation}",
            ]
        )
        if finding.evidence:
            lines.append(f"Evidence: {finding.evidence}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-release-guardian", description="Scan release artifacts for AI-era leaks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan a release artifact, directory, archive, or npm pack JSON.")
    scan.add_argument("path", help="Path to directory, file, zip, tar/tgz, gzip, or npm pack --json output.")
    scan.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    scan.add_argument("--fail-on", choices=("medium", "high", "critical"), default="high", help="Minimum severity that returns exit code 1.")
    scan.add_argument("--allowlist", help="Path to JSON allowlist with rule_id, path, and reason entries.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = scan_path(args.path, args.allowlist)
    except (FileNotFoundError, ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"ai-release-guardian: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    threshold = Severity.from_text(args.fail_on)
    return 1 if result.has_failures(threshold) else 0


if __name__ == "__main__":
    raise SystemExit(main())
