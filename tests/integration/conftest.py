from __future__ import annotations

import os
import urllib.request
from typing import Any

import pytest


def get_localstack_endpoint() -> str | None:
    override = os.environ.get("LOCALSTACK_ENDPOINT_URL")
    endpoints = [override] if override else ["http://127.0.0.1:4566", "http://localhost:4566"]
    for endpoint in endpoints:
        try:
            response = urllib.request.urlopen(f"{endpoint}/_localstack/health", timeout=2)
            if response.status == 200:
                return endpoint
        except Exception:
            pass
    return None


@pytest.fixture(scope="session")
def localstack_endpoint() -> str:
    endpoint = get_localstack_endpoint()
    if endpoint is None:
        pytest.skip("LocalStack container is not reachable on 4566")
    return endpoint


@pytest.fixture(scope="session")
def aws_credentials() -> dict[str, str]:
    return {
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
        "region_name": "us-east-1",
    }


@pytest.fixture(scope="session")
def s3_client(localstack_endpoint: str, aws_credentials: dict[str, str]) -> Any:
    import boto3

    return boto3.client("s3", endpoint_url=localstack_endpoint, **aws_credentials)


@pytest.fixture(scope="session")
def ssm_client(localstack_endpoint: str, aws_credentials: dict[str, str]) -> Any:
    import boto3

    return boto3.client("ssm", endpoint_url=localstack_endpoint, **aws_credentials)


@pytest.fixture(scope="session")
def ec2_client(localstack_endpoint: str, aws_credentials: dict[str, str]) -> Any:
    import boto3

    return boto3.client("ec2", endpoint_url=localstack_endpoint, **aws_credentials)


@pytest.fixture(scope="session")
def stepfunctions_client(localstack_endpoint: str, aws_credentials: dict[str, str]) -> Any:
    import boto3

    return boto3.client("stepfunctions", endpoint_url=localstack_endpoint, **aws_credentials)
