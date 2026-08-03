from pathlib import Path

ROOT = Path(__file__).parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_readme_presents_the_production_gamewake_architecture_and_handoff():
    readme = read("README.md")

    assert "Aurora PostgreSQL Serverless v2" in readme
    assert "Step Functions Standard" in readme
    assert "AbacatePay" in readme
    assert "docs/DEPLOYMENT.md" in readme
    assert "docs/MVP_AUDIT.md" in readme
    assert "/palworld ligar" not in readme


def test_delivery_documents_cover_deployment_operations_and_external_launch_gates():
    deployment = read("docs/DEPLOYMENT.md")
    audit = read("docs/MVP_AUDIT.md")

    assert "NEXT_PUBLIC_GAMEWAKE_API_URL" in deployment
    assert "gamewake_api.discord_interactions" in deployment
    assert "AbacatePay API v2" in deployment
    assert "Aurora PostgreSQL Serverless v2" in deployment
    assert "Step Functions Standard" in deployment
    assert "GAMEWAKE_TEST_DATABASE_URL" in deployment

    assert "Requisitos externos" in audit
    assert "Closed Beta" in audit
    assert "deploy real" in audit

    for runbook in (
        "docs/runbooks/first-deploy.md",
        "docs/runbooks/stuck-operation.md",
        "docs/runbooks/payment-reconciliation.md",
        "docs/runbooks/world-restore-export.md",
        "docs/runbooks/owner-recovery.md",
        "docs/runbooks/incident-response.md",
    ):
        assert (ROOT / runbook).is_file()


def test_terraform_handoff_uses_gamewake_endpoints_and_commands():
    outputs = read("terraform/outputs.tf")

    assert "gamewake_api.discord_interactions" in outputs
    assert "gamewake_api.discord_oauth_callback" in outputs
    assert "/gamewake comecar" in outputs
    assert "/palworld ligar" not in outputs


def test_abacatepay_setup_uses_and_validates_the_documented_public_hmac_key():
    env_example = read(".env.example")
    configure_secrets = read("scripts/configure-secrets.sh")

    assert (
        "ABACATEPAY_PUBLIC_KEY="
        "t9dXRhHHo3yDEj5pVDYz0frf7q6bMKyMRmxxCPIPp3RCplBfXRxqlC6ZpiWmOqj4L63qEaeUOtrCI8P0VMUgo6iIga2ri9ogaHFs0WIIywSMg0q7RmBfybe1E5XJcfC4IW3alNqym0tXoAKkzvfEjZxV6bE0oG2zJrNNYmUCKZyV0KZ3JS8Votf9EAWWYdiDkMkpbMdPggfh1EqHlVkMiTady6jOR3hyzGEHrIz2Ret0xHKMbiqkr9HS1JhNHDX9"
    ) in env_example
    assert "${#ABACATEPAY_PUBLIC_KEY} < 200" in configure_secrets
    assert "chave HMAC publica longa" in configure_secrets
