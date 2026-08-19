from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.security.collect_findings import (
    assert_report_is_clean,
    collect_codeql,
    collect_trivy,
    collect_zap,
    load_report,
    load_zap_ignored_rule_ids,
    new_report,
)
from scripts.security.sync_github_issues import SecurityIssueContext, sync_security_issues


class FakeGitHubIssues:
    def __init__(self) -> None:
        self.issues: list[dict[str, object]] = []

    def ensure_labels(self) -> None:
        return None

    def list_security_issues(self) -> list[dict[str, object]]:
        return list(self.issues)

    def create_issue(self, *, title: str, body: str) -> dict[str, object]:
        issue = {
            "number": len(self.issues) + 1,
            "title": title,
            "body": body,
            "state": "open",
        }
        self.issues.append(issue)
        return issue

    def update_issue(
        self,
        number: int,
        *,
        title: str,
        body: str,
        state: str,
    ) -> None:
        issue = next(item for item in self.issues if item["number"] == number)
        issue.update(title=title, body=body, state=state)


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_codeql_collects_only_high_or_critical_security_results(tmp_path: Path) -> None:
    sarif = {
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": "py/high",
                                "shortDescription": {"text": "High risk flow"},
                                "properties": {"security-severity": "8.2"},
                            },
                            {
                                "id": "py/medium",
                                "shortDescription": {"text": "Medium risk flow"},
                                "properties": {"security-severity": "5.0"},
                            },
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "py/high",
                        "message": {"text": "Untrusted data reaches a sink"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "gamewake/api.py"},
                                    "region": {"startLine": 42},
                                }
                            }
                        ],
                    },
                    {
                        "ruleId": "py/medium",
                        "message": {"text": "Lower severity result"},
                    },
                ],
            }
        ]
    }

    findings = collect_codeql([_write_json(tmp_path / "codeql.sarif", sarif)])

    assert len(findings) == 1
    assert findings[0]["category"] == "SAST"
    assert findings[0]["severity"] == "HIGH"
    assert findings[0]["location"] == "gamewake/api.py:42"


def test_trivy_collects_sca_iac_and_redacts_secret_values(tmp_path: Path) -> None:
    payload = {
        "Results": [
            {
                "Target": "web/package-lock.json",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-0001",
                        "PkgName": "example",
                        "InstalledVersion": "1.0.0",
                        "FixedVersion": "1.0.1",
                        "Severity": "HIGH",
                        "Title": "Example dependency vulnerability",
                    }
                ],
            },
            {
                "Target": "terraform/main.tf",
                "Misconfigurations": [
                    {
                        "ID": "AVD-AWS-9999",
                        "Severity": "CRITICAL",
                        "Title": "Unsafe cloud configuration",
                        "Message": "A protected resource is public",
                        "Resolution": "Restrict the resource policy",
                        "CauseMetadata": {"StartLine": 12},
                    }
                ],
                "Secrets": [
                    {
                        "RuleID": "private-key",
                        "Severity": "CRITICAL",
                        "Title": "Private key",
                        "StartLine": 7,
                        "Match": "DO-NOT-LEAK-THIS-SECRET",
                    }
                ],
            },
        ]
    }

    findings = collect_trivy(_write_json(tmp_path / "trivy.json", payload))
    rendered = json.dumps(findings)

    assert {finding["category"] for finding in findings} == {"SAST", "SCA"}
    assert "CVE-2026-0001" in rendered
    assert "AVD-AWS-9999" in rendered
    assert "DO-NOT-LEAK-THIS-SECRET" not in rendered


def test_zap_collects_medium_or_higher_and_removes_query_strings(tmp_path: Path) -> None:
    payload = {
        "site": [
            {
                "alerts": [
                    {
                        "pluginid": "10020",
                        "riskcode": "2",
                        "riskdesc": "Medium (High)",
                        "name": "Missing anti-clickjacking header",
                        "desc": "The response can be framed.",
                        "solution": "Set a frame-ancestors policy.",
                        "instances": [
                            {
                                "uri": "http://127.0.0.1:3000/account?token=sensitive",
                            }
                        ],
                    },
                    {
                        "pluginid": "10021",
                        "riskcode": "1",
                        "name": "Low risk header",
                    },
                    {
                        "pluginid": "90003",
                        "riskcode": "2",
                        "name": "Accepted same-origin SRI signal",
                    },
                ]
            }
        ]
    }
    rules = tmp_path / "zap-rules.tsv"
    rules.write_text(
        "90003\tIGNORE\t(Same-origin assets)\n10020\tWARN\t(Actionable header)\n",
        encoding="utf-8",
    )

    findings = collect_zap(
        _write_json(tmp_path / "zap.json", payload),
        ignored_rule_ids=load_zap_ignored_rule_ids(rules),
    )

    assert len(findings) == 1
    assert findings[0]["category"] == "DAST"
    assert findings[0]["location"] == "http://127.0.0.1:3000/account"
    assert "sensitive" not in json.dumps(findings)


def test_security_report_fails_the_gate_when_findings_exist() -> None:
    report = new_report(
        source="security-checks",
        scanned_categories=["SCA"],
        findings=[
            {
                "category": "SCA",
                "scanner": "Trivy",
                "severity": "HIGH",
                "rule_id": "CVE-2026-0001",
                "title": "Dependency vulnerability",
                "location": "web/package-lock.json",
                "description": "Upgrade the dependency.",
                "remediation": "Use the fixed release.",
                "reference": "",
            }
        ],
    )

    with pytest.raises(SystemExit):
        assert_report_is_clean(report)


def test_security_report_rejects_untrusted_source_and_classification(tmp_path: Path) -> None:
    invalid_source = {
        "schema_version": 1,
        "source": "../../untrusted",
        "scanned_categories": ["SAST"],
        "findings": [],
    }
    with pytest.raises(ValueError, match="source"):
        load_report(_write_json(tmp_path / "invalid-source.json", invalid_source))

    invalid_classification = {
        "schema_version": 1,
        "source": "security-checks",
        "scanned_categories": ["SAST"],
        "findings": [
            {
                "category": "ARBITRARY",
                "severity": "CRITICAL",
                "scanner": "untrusted",
            }
        ],
    }
    with pytest.raises(ValueError, match="classification"):
        load_report(_write_json(tmp_path / "invalid-classification.json", invalid_classification))


def test_issue_sync_deduplicates_by_source_and_never_auto_closes() -> None:
    github = FakeGitHubIssues()
    context = SecurityIssueContext(
        repository="SchunckLeonardo/game-wake",
        run_url="https://github.com/SchunckLeonardo/game-wake/actions/runs/1",
        event_name="pull_request",
        head_sha="a" * 40,
    )
    vulnerable = new_report(
        source="security-checks",
        scanned_categories=["SCA"],
        findings=[
            {
                "category": "SCA",
                "scanner": "Trivy",
                "severity": "HIGH",
                "rule_id": "CVE-2026-0001",
                "title": "Dependency vulnerability",
                "location": "web/package-lock.json",
                "description": "Upgrade the dependency.",
                "remediation": "Use the fixed release.",
                "reference": "",
            }
        ],
    )

    sync_security_issues(vulnerable, context=context, github=github)
    sync_security_issues(vulnerable, context=context, github=github)

    assert len(github.issues) == 1
    assert github.issues[0]["state"] == "open"
    assert "<!-- gamewake-security:security-checks:SCA -->" in str(github.issues[0]["body"])

    clean = new_report(
        source="security-checks",
        scanned_categories=["SCA"],
        findings=[],
    )
    sync_security_issues(clean, context=context, github=github)
    assert github.issues[0]["state"] == "open"

    codeql = new_report(
        source="codeql",
        scanned_categories=["SAST"],
        findings=[
            {
                **vulnerable["findings"][0],
                "category": "SAST",
                "scanner": "CodeQL",
            }
        ],
    )
    sync_security_issues(codeql, context=context, github=github)

    assert len(github.issues) == 2
    assert all(issue["state"] == "open" for issue in github.issues)


def test_security_workflows_cover_pr_main_and_isolate_issue_writes() -> None:
    security = Path(".github/workflows/security.yml").read_text(encoding="utf-8")
    reporter = Path(".github/workflows/security-issues.yml").read_text(encoding="utf-8")
    codeql = Path(".github/workflows/codeql.yml").read_text(encoding="utf-8")
    zap_rules = Path("web/zap-rules.tsv").read_text(encoding="utf-8")

    assert "pull_request:" in security
    assert "push:" in security
    assert "branches: [main]" in security
    assert "Security gate" in security
    assert "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25" in security
    assert "version: v0.74.0" in security
    assert 'TRIVY_INCLUDE_DEV_DEPS: "true"' in security
    assert security.count("trivyignores: .trivyignore.yaml") == 2
    assert security.count("mkdir -p reports") == 2
    assert "zaproxy/action-baseline@de8ad967d3548d44ef623df22cf95c3b0baf8b25" in security
    assert "target: http://localhost:3000" in security
    assert "curl --fail --silent --show-error http://localhost:3000/" in security
    assert "rules_file_name: web/zap-rules.tsv" in security
    assert "--zap-rules web/zap-rules.tsv" in security
    assert "10055\tIGNORE\t" in zap_rules
    assert "allow_issue_writing: false" in security
    assert "pull_request_target" not in security + reporter

    assert "workflow_run:" in reporter
    assert "issues: write" in reporter
    assert "python3 -m scripts.security.sync_github_issues" in reporter
    assert "persist-credentials: false" in reporter
    assert "github.event.repository.default_branch" in reporter
    assert "ref: ${{ github.event.workflow_run.head_sha }}" not in reporter

    assert "security-findings" in codeql
    assert "collect_findings.py codeql" in codeql
