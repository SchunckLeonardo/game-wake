from __future__ import annotations

import argparse
import glob
import html
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = 1
SUPPORTED_CATEGORIES = ("SAST", "SCA", "DAST")
SEVERITY_ORDER = {"MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _text(value: object, *, limit: int = 800) -> str:
    rendered = html.unescape(str(value or ""))
    rendered = re.sub(r"<[^>]+>", " ", rendered)
    rendered = re.sub(r"\s+", " ", rendered).strip()
    return rendered[:limit]


def _safe_url(value: object) -> str:
    rendered = _text(value, limit=2_000)
    if not rendered:
        return ""
    try:
        parsed = urlsplit(rendered)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _location(path: object, line: object = None) -> str:
    rendered = _text(path, limit=500)
    if isinstance(line, int) and line > 0:
        return f"{rendered}:{line}"
    return rendered


def _finding(
    *,
    category: str,
    scanner: str,
    severity: str,
    rule_id: object,
    title: object,
    location: object,
    description: object,
    remediation: object = "",
    reference: object = "",
) -> dict[str, str]:
    return {
        "category": category,
        "scanner": _text(scanner, limit=80),
        "severity": severity,
        "rule_id": _text(rule_id, limit=160),
        "title": _text(title, limit=300),
        "location": _text(location, limit=500),
        "description": _text(description),
        "remediation": _text(remediation),
        "reference": _safe_url(reference),
    }


def _deduplicate(findings: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for finding in findings:
        key = (
            finding["category"],
            finding["scanner"],
            finding["rule_id"],
            finding["location"],
        )
        unique[key] = finding
    return sorted(
        unique.values(),
        key=lambda item: (
            item["category"],
            -SEVERITY_ORDER.get(item["severity"], 0),
            item["scanner"],
            item["rule_id"],
            item["location"],
        ),
    )


def collect_codeql(paths: Iterable[Path]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        for run in document.get("runs", []):
            driver = run.get("tool", {}).get("driver", {})
            rules = {rule.get("id"): rule for rule in driver.get("rules", [])}
            scanner = driver.get("name") or "CodeQL"
            for result in run.get("results", []):
                rule_id = result.get("ruleId", "unknown")
                rule = rules.get(rule_id, {})
                raw_score = rule.get("properties", {}).get("security-severity")
                try:
                    score = float(raw_score)
                except (TypeError, ValueError):
                    continue
                if score < 7.0:
                    continue
                severity = "CRITICAL" if score >= 9.0 else "HIGH"
                physical = (result.get("locations") or [{}])[0].get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {}).get("uri", "")
                line = physical.get("region", {}).get("startLine")
                title = rule.get("shortDescription", {}).get("text") or rule.get("name") or rule_id
                findings.append(
                    _finding(
                        category="SAST",
                        scanner=scanner,
                        severity=severity,
                        rule_id=rule_id,
                        title=title,
                        location=_location(artifact, line),
                        description=result.get("message", {}).get("text", ""),
                        remediation=rule.get("help", {}).get("text", ""),
                        reference=rule.get("helpUri", ""),
                    )
                )
    return _deduplicate(findings)


def collect_trivy(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    findings: list[dict[str, str]] = []
    for result in document.get("Results") or []:
        target = result.get("Target", "")
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = _text(vulnerability.get("Severity")).upper()
            if severity not in {"HIGH", "CRITICAL"}:
                continue
            package = _text(vulnerability.get("PkgName"), limit=200)
            installed = _text(vulnerability.get("InstalledVersion"), limit=100)
            fixed = _text(vulnerability.get("FixedVersion"), limit=100)
            remediation = f"Atualize {package} para {fixed}." if fixed else ""
            findings.append(
                _finding(
                    category="SCA",
                    scanner="Trivy",
                    severity=severity,
                    rule_id=vulnerability.get("VulnerabilityID"),
                    title=vulnerability.get("Title") or package,
                    location=target,
                    description=(
                        f"Pacote {package} na versão {installed}. "
                        f"{vulnerability.get('Description', '')}"
                    ),
                    remediation=remediation,
                    reference=vulnerability.get("PrimaryURL"),
                )
            )
        for misconfiguration in result.get("Misconfigurations") or []:
            severity = _text(misconfiguration.get("Severity")).upper()
            if severity not in {"HIGH", "CRITICAL"}:
                continue
            line = misconfiguration.get("CauseMetadata", {}).get("StartLine")
            findings.append(
                _finding(
                    category="SAST",
                    scanner="Trivy IaC",
                    severity=severity,
                    rule_id=misconfiguration.get("ID"),
                    title=misconfiguration.get("Title"),
                    location=_location(target, line),
                    description=misconfiguration.get("Message"),
                    remediation=misconfiguration.get("Resolution"),
                    reference=misconfiguration.get("PrimaryURL"),
                )
            )
        for secret in result.get("Secrets") or []:
            severity = _text(secret.get("Severity")).upper()
            if severity not in {"HIGH", "CRITICAL"}:
                continue
            findings.append(
                _finding(
                    category="SAST",
                    scanner="Trivy Secret",
                    severity=severity,
                    rule_id=secret.get("RuleID"),
                    title=secret.get("Title") or "Possível segredo versionado",
                    location=_location(target, secret.get("StartLine")),
                    description=(
                        "Um padrão compatível com segredo foi encontrado. "
                        "O valor foi omitido deliberadamente do relatório."
                    ),
                    remediation="Revogue o valor, remova-o do código e use armazenamento seguro.",
                )
            )
    return _deduplicate(findings)


def collect_zap(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    findings: list[dict[str, str]] = []
    for site in document.get("site") or []:
        for alert in site.get("alerts") or []:
            try:
                risk_code = int(alert.get("riskcode", 0))
            except (TypeError, ValueError):
                continue
            if risk_code < 2:
                continue
            severity = "HIGH" if risk_code >= 3 else "MEDIUM"
            instance = (alert.get("instances") or [{}])[0]
            findings.append(
                _finding(
                    category="DAST",
                    scanner="OWASP ZAP",
                    severity=severity,
                    rule_id=alert.get("pluginid"),
                    title=alert.get("name"),
                    location=_safe_url(instance.get("uri")),
                    description=alert.get("desc"),
                    remediation=alert.get("solution"),
                    reference=alert.get("reference"),
                )
            )
    return _deduplicate(findings)


def new_report(
    *,
    source: str,
    scanned_categories: Iterable[str],
    findings: Iterable[dict[str, str]],
) -> dict[str, object]:
    if not re.fullmatch(r"[a-z0-9-]+", source):
        raise ValueError("Invalid security report source")
    categories = sorted(set(scanned_categories))
    unsupported = set(categories).difference(SUPPORTED_CATEGORIES)
    if unsupported:
        raise ValueError(f"Unsupported security categories: {sorted(unsupported)}")
    normalized = _deduplicate(findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "scanned_categories": categories,
        "findings": normalized,
    }


def load_report(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported security report schema")
    source = document.get("source")
    categories = document.get("scanned_categories")
    findings = document.get("findings")
    if (
        not isinstance(source, str)
        or not isinstance(categories, list)
        or not isinstance(findings, list)
    ):
        raise ValueError("Invalid security report")
    if len(findings) > 2_000:
        raise ValueError("Security report exceeds the findings limit")
    if any(not isinstance(category, str) for category in categories):
        raise ValueError("Invalid security report categories")
    sanitized_findings: list[dict[str, str]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("Invalid security finding")
        category = finding.get("category")
        severity = finding.get("severity")
        if category not in SUPPORTED_CATEGORIES or severity not in SEVERITY_ORDER:
            raise ValueError("Invalid security finding classification")
        sanitized_findings.append(
            _finding(
                category=category,
                scanner=finding.get("scanner"),
                severity=severity,
                rule_id=finding.get("rule_id"),
                title=finding.get("title"),
                location=finding.get("location"),
                description=finding.get("description"),
                remediation=finding.get("remediation"),
                reference=finding.get("reference"),
            )
        )
    return new_report(
        source=source,
        scanned_categories=categories,
        findings=sanitized_findings,
    )


def write_report(report: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assert_report_is_clean(report: dict[str, object]) -> None:
    findings = report.get("findings") or []
    if findings:
        counts: dict[str, int] = {}
        for finding in findings:
            category = str(finding.get("category", "UNKNOWN"))
            counts[category] = counts.get(category, 0) + 1
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        print(f"Security gate failed: {summary}", file=sys.stderr)
        raise SystemExit(1)
    print("Security gate passed: no actionable findings.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize security scanner reports")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codeql = subparsers.add_parser("codeql")
    codeql.add_argument("--sarif-glob", required=True)
    codeql.add_argument("--output", type=Path, required=True)

    security = subparsers.add_parser("security")
    security.add_argument("--trivy-sast", type=Path, required=True)
    security.add_argument("--trivy-sca", type=Path, required=True)
    security.add_argument("--zap", type=Path, required=True)
    security.add_argument("--output", type=Path, required=True)

    gate = subparsers.add_parser("assert")
    gate.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "codeql":
        paths = [Path(item) for item in glob.glob(args.sarif_glob, recursive=True)]
        report = new_report(
            source="codeql",
            scanned_categories=["SAST"],
            findings=collect_codeql(paths),
        )
        write_report(report, args.output)
        return 0
    if args.command == "security":
        findings = [
            *collect_trivy(args.trivy_sast),
            *collect_trivy(args.trivy_sca),
            *collect_zap(args.zap),
        ]
        report = new_report(
            source="security-checks",
            scanned_categories=SUPPORTED_CATEGORIES,
            findings=findings,
        )
        write_report(report, args.output)
        return 0
    report = load_report(args.report)
    assert_report_is_clean(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
