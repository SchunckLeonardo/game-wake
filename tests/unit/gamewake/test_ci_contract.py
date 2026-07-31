from pathlib import Path

ROOT = Path(__file__).parents[3]


def read(path):
    return (ROOT / path).read_text()


def test_ci_runs_unit_postgres_web_and_browser_acceptance_suites():
    workflow = read(".github/workflows/tests.yml")

    assert "unit-tests:" in workflow
    assert "postgres-integration:" in workflow
    assert "postgres:16-alpine" in workflow
    assert "GAMEWAKE_TEST_DATABASE_URL" in workflow
    assert "web-quality:" in workflow
    assert "web-e2e:" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "npx playwright install --with-deps chromium" in workflow
    assert "POSTGRES_INTEGRATION_RESULT" in workflow
    assert "WEB_E2E_RESULT" in workflow


def test_codeql_analyzes_python_and_typescript():
    workflow = read(".github/workflows/codeql.yml")

    assert "languages: python,javascript-typescript" in workflow


def test_terraform_workflows_initialize_the_remote_s3_backend_from_environment_vars():
    versions = read("terraform/versions.tf")
    plan = read(".github/workflows/terraform-plan.yml")
    apply = read(".github/workflows/terraform-apply.yml")

    assert 'backend "s3" {}' in versions
    for workflow in (plan, apply):
        assert "TF_STATE_BUCKET" in workflow
        assert "TF_STATE_KEY" in workflow
        assert "use_lockfile=true" in workflow


def test_local_quality_commands_cover_the_gamewake_backend_and_web_console():
    makefile = read("Makefile")
    validation = read("scripts/validate.sh")

    assert "gamewake lambda server scripts shared tests palworld" in makefile
    assert "npm --prefix web run lint" in makefile
    assert "gamewake lambda server scripts shared tests palworld" in validation
    assert "npm --prefix web run test" in validation
