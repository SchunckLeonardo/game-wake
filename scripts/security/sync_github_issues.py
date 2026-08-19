from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.security.collect_findings import SUPPORTED_CATEGORIES, load_report

ISSUE_LABEL = "security-automation"
SECURITY_LABEL = "security"
MAX_BODY_FINDINGS = 50


@dataclass(frozen=True)
class SecurityIssueContext:
    repository: str
    run_url: str
    event_name: str
    head_sha: str


class GitHubIssuesPort(Protocol):
    def ensure_labels(self) -> None: ...

    def list_security_issues(self) -> list[dict[str, object]]: ...

    def create_issue(self, *, title: str, body: str) -> dict[str, object]: ...

    def update_issue(
        self,
        number: int,
        *,
        title: str,
        body: str,
        state: str,
    ) -> None: ...


class GitHubIssues:
    def __init__(self, *, repository: str, token: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub repository")
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self._repository = repository
        self._token = token
        self._base_url = f"https://api.github.com/repos/{repository}"

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> object | None:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "gamewake-security-automation",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            if allow_not_found and error.code == 404:
                return None
            message = error.read().decode(errors="replace")[:1_000]
            raise RuntimeError(f"GitHub API returned {error.code}: {message}") from error
        return json.loads(raw) if raw else None

    def ensure_labels(self) -> None:
        labels = {
            SECURITY_LABEL: ("b60205", "Vulnerabilidade ou hardening de segurança"),
            ISSUE_LABEL: ("5319e7", "Issue mantida automaticamente pelos security checks"),
        }
        for name, (color, description) in labels.items():
            encoded = urllib.parse.quote(name, safe="")
            existing = self._request(
                "GET",
                f"/labels/{encoded}",
                allow_not_found=True,
            )
            if existing is None:
                self._request(
                    "POST",
                    "/labels",
                    {"name": name, "color": color, "description": description},
                )

    def list_security_issues(self) -> list[dict[str, object]]:
        query = urllib.parse.urlencode({"state": "all", "labels": ISSUE_LABEL, "per_page": "100"})
        response = self._request("GET", f"/issues?{query}")
        if not isinstance(response, list):
            raise RuntimeError("GitHub issues response was not a list")
        return [item for item in response if "pull_request" not in item]

    def create_issue(self, *, title: str, body: str) -> dict[str, object]:
        response = self._request(
            "POST",
            "/issues",
            {
                "title": title,
                "body": body,
                "labels": [SECURITY_LABEL, ISSUE_LABEL],
            },
        )
        if not isinstance(response, dict):
            raise RuntimeError("GitHub issue creation returned an invalid response")
        return response

    def update_issue(
        self,
        number: int,
        *,
        title: str,
        body: str,
        state: str,
    ) -> None:
        payload: dict[str, object] = {
            "title": title,
            "body": body,
            "state": state,
            "labels": [SECURITY_LABEL, ISSUE_LABEL],
        }
        if state == "closed":
            payload["state_reason"] = "completed"
        self._request("PATCH", f"/issues/{number}", payload)


def _marker(source: str, category: str) -> str:
    return f"<!-- gamewake-security:{source}:{category} -->"


def _source_name(source: str, category: str) -> str:
    if source == "codeql":
        return "CodeQL"
    if category == "DAST":
        return "ZAP"
    return "Trivy"


def _title(source: str, category: str) -> str:
    return f"[Security][{category}][{_source_name(source, category)}] Vulnerabilidades"


def _markdown(value: object, *, limit: int = 240) -> str:
    rendered = re.sub(r"\s+", " ", str(value or "")).strip()
    return rendered.replace("|", "\\|").replace("`", "'")[:limit]


def _body(
    source: str,
    category: str,
    findings: list[dict[str, str]],
    context: SecurityIssueContext,
) -> str:
    lines = [
        _marker(source, category),
        f"# Achados automáticos de {category} · {_source_name(source, category)}",
        "",
        (
            "Esta issue é mantida automaticamente pelos security checks do GameWake. "
            "Ela é atualizada quando o mesmo scanner encontra novos achados. Feche-a "
            "somente depois de corrigir e validar a execução indicada."
        ),
        "",
        f"- Execução: [abrir no GitHub Actions]({context.run_url})",
        f"- Evento: `{_markdown(context.event_name)}`",
        f"- Commit: `{_markdown(context.head_sha[:12])}`",
        f"- Total: **{len(findings)}**",
        "",
        "| Severidade | Scanner | Regra | Local | Achado |",
        "|---|---|---|---|---|",
    ]
    for finding in findings[:MAX_BODY_FINDINGS]:
        lines.append(
            "| {severity} | {scanner} | {rule} | {location} | {title} |".format(
                severity=_markdown(finding.get("severity")),
                scanner=_markdown(finding.get("scanner")),
                rule=_markdown(finding.get("rule_id")),
                location=_markdown(finding.get("location")),
                title=_markdown(finding.get("title")),
            )
        )
    if len(findings) > MAX_BODY_FINDINGS:
        lines.extend(
            [
                "",
                f"Mais {len(findings) - MAX_BODY_FINDINGS} achados estão no artefato do workflow.",
            ]
        )
    lines.extend(
        [
            "",
            "## Como corrigir",
            "",
            "Abra a execução acima, consulte o artefato `security-findings` e trate os "
            "achados de maior severidade primeiro. Não publique segredos ou dados sensíveis "
            "nos comentários desta issue.",
        ]
    )
    return "\n".join(lines) + "\n"


def sync_security_issues(
    report: dict[str, object],
    *,
    context: SecurityIssueContext,
    github: GitHubIssuesPort,
) -> None:
    categories = report.get("scanned_categories")
    findings = report.get("findings")
    source = report.get("source")
    if (
        not isinstance(source, str)
        or not isinstance(categories, list)
        or not isinstance(findings, list)
    ):
        raise ValueError("Invalid security report")
    github.ensure_labels()
    existing = github.list_security_issues()
    by_category: dict[str, dict[str, object]] = {}
    for category in SUPPORTED_CATEGORIES:
        marker = _marker(source, category)
        match = next((issue for issue in existing if marker in str(issue.get("body", ""))), None)
        if match is not None:
            by_category[category] = match

    for category in categories:
        if category not in SUPPORTED_CATEGORIES:
            raise ValueError(f"Unsupported category: {category}")
        category_findings = [
            finding
            for finding in findings
            if isinstance(finding, dict) and finding.get("category") == category
        ]
        issue = by_category.get(category)
        if category_findings:
            body = _body(source, category, category_findings, context)
            if issue is None:
                github.create_issue(title=_title(source, category), body=body)
            else:
                github.update_issue(
                    int(issue["number"]),
                    title=_title(source, category),
                    body=body,
                    state="open",
                )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize security findings with GitHub issues")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.report.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Security report is larger than 5 MiB")
    report = load_report(args.report)
    context = SecurityIssueContext(
        repository=args.repository,
        run_url=args.run_url,
        event_name=args.event_name,
        head_sha=args.head_sha,
    )
    github = GitHubIssues(
        repository=context.repository,
        token=os.environ.get("GITHUB_TOKEN", ""),
    )
    sync_security_issues(report, context=context, github=github)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
