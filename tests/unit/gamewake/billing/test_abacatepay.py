import json
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

import gamewake.billing as billing_package
from gamewake.billing import ContributionCheckoutRequest
from gamewake.billing.abacatepay import (
    AbacatePayPaymentProvider,
    AbacatePayWebhookHandler,
    InvalidWebhookSignature,
    UrllibJsonHttpClient,
)


class JsonResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return b'{"success": true, "data": []}'


def test_abacatepay_adapters_are_exposed_by_the_billing_public_api():
    assert billing_package.AbacatePayPaymentProvider is AbacatePayPaymentProvider
    assert billing_package.AbacatePayWebhookHandler is AbacatePayWebhookHandler


def test_urllib_client_identifies_gamewake_instead_of_using_the_blocked_python_agent():
    captured = {}

    def open_request(request, *, timeout):
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return JsonResponse()

    with patch("gamewake.billing.abacatepay.urlopen", side_effect=open_request):
        response = UrllibJsonHttpClient().request(
            "GET",
            "https://api.abacatepay.com/v2/checkouts/list?limit=1",
            headers={"Authorization": "Bearer test-key"},
            json_body=None,
        )

    assert response == {"success": True, "data": []}
    assert captured == {
        "user_agent": "GameWake/0.1.0 (+https://gamewake.com.br)",
        "timeout": 15,
    }


class RecordingHttpClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, url, *, headers, json_body=None):
        self.requests.append((method, url, headers, json_body))
        return self.response


def test_checkout_uses_the_configured_credit_product_and_only_the_available_pix_method():
    http = RecordingHttpClient(
        {
            "success": True,
            "error": None,
            "data": {
                "id": "bill_123",
                "externalId": "contribution-1",
                "url": "https://app.abacatepay.com/pay/bill_123",
                "amount": 5000,
                "status": "PENDING",
            },
        }
    )
    provider = AbacatePayPaymentProvider(api_key="test-key", http_client=http)

    checkout = provider.create_checkout(
        ContributionCheckoutRequest(
            external_id="contribution-1",
            provider_product_id="prod_50_brl",
            expected_amount=Decimal("50.00"),
            return_url="https://gamewake.example/wallet",
            completion_url="https://gamewake.example/wallet/success",
        )
    )

    assert checkout.id == "bill_123"
    assert checkout.amount == Decimal("50.00")
    assert checkout.url == "https://app.abacatepay.com/pay/bill_123"
    assert http.requests == [
        (
            "POST",
            "https://api.abacatepay.com/v2/checkouts/create",
            {
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            {
                "items": [{"id": "prod_50_brl", "quantity": 1}],
                "methods": ["PIX"],
                "externalId": "contribution-1",
                "returnUrl": "https://gamewake.example/wallet",
                "completionUrl": "https://gamewake.example/wallet/success",
                "metadata": {"gamewakeContributionId": "contribution-1"},
            },
        )
    ]


def test_checkout_prefills_the_verified_customer_information_that_gamewake_already_has():
    class SequencedHttpClient:
        def __init__(self):
            self.requests = []

        def request(self, method, url, *, headers, json_body=None):
            self.requests.append((method, url, headers, json_body))
            if url.endswith("/customers/create"):
                return {
                    "success": True,
                    "error": None,
                    "data": {"id": "cust_leonardo"},
                }
            return {
                "success": True,
                "error": None,
                "data": {
                    "id": "bill_123",
                    "externalId": "contribution-1",
                    "url": "https://app.abacatepay.com/pay/bill_123",
                    "amount": 5000,
                    "status": "PENDING",
                },
            }

    http = SequencedHttpClient()
    provider = AbacatePayPaymentProvider(api_key="test-key", http_client=http)

    provider.create_checkout(
        ContributionCheckoutRequest(
            external_id="contribution-1",
            provider_product_id="prod_50_brl",
            expected_amount=Decimal("50.00"),
            return_url="https://gamewake.example/wallet",
            completion_url="https://gamewake.example/wallet/success",
            payer_name="Leonardo",
            payer_email="leo@example.com",
        )
    )

    assert http.requests[0][0:2] == (
        "POST",
        "https://api.abacatepay.com/v2/customers/create",
    )
    assert http.requests[0][3] == {
        "email": "leo@example.com",
        "name": "Leonardo",
        "metadata": {"gamewakeContributionId": "contribution-1"},
    }
    assert http.requests[1][3]["customerId"] == "cust_leonardo"


def test_urllib_client_preserves_the_safe_abacatepay_error_for_diagnostics():
    error = HTTPError(
        "https://api.abacatepay.com/v2/checkouts/create",
        400,
        "Bad Request",
        {},
        BytesIO(b'{"success":false,"error":"CARD is not available for this store","data":null}'),
    )

    with (
        patch("gamewake.billing.abacatepay.urlopen", side_effect=error),
        pytest.raises(
            RuntimeError,
            match=r"AbacatePay request failed \(400\): CARD is not available for this store",
        ),
    ):
        UrllibJsonHttpClient().request(
            "POST",
            "https://api.abacatepay.com/v2/checkouts/create",
            headers={"Authorization": "Bearer test-key"},
            json_body={"items": [{"id": "prod_25_brl", "quantity": 1}]},
        )


def test_webhook_rejects_an_invalid_signature_before_processing_the_event():
    processed = []
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=processed.append,
    )
    raw_body = json.dumps({"id": "log_1", "event": "checkout.completed", "data": {}}).encode()

    with pytest.raises(InvalidWebhookSignature) as caught:
        handler.handle(
            raw_body,
            webhook_secret="url-secret",
            signature="forged-signature",
        )

    assert caught.value.layer == "hmac_signature"
    assert processed == []


def test_webhook_reports_a_url_secret_mismatch_without_parsing_the_event():
    processed = []
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=processed.append,
    )

    with pytest.raises(InvalidWebhookSignature) as caught:
        handler.handle(
            b"not-json",
            webhook_secret="wrong-secret",
            signature="forged-signature",
        )

    assert caught.value.layer == "url_secret"
    assert processed == []


def test_refund_requests_the_documented_full_checkout_refund():
    http = RecordingHttpClient(
        {
            "success": True,
            "error": None,
            "data": {"refundPublicId": "tran_refund_123"},
        }
    )
    provider = AbacatePayPaymentProvider(api_key="test-key", http_client=http)

    refund_id = provider.refund_checkout(
        "bill_123",
        reason="Créditos não utilizados",
    )

    assert refund_id == "tran_refund_123"
    assert http.requests == [
        (
            "POST",
            "https://api.abacatepay.com/v2/checkouts/refund",
            {
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            {"id": "bill_123", "reason": "Créditos não utilizados"},
        )
    ]


def test_checkout_can_be_recovered_by_its_external_id():
    http = RecordingHttpClient(
        {
            "success": True,
            "error": None,
            "data": [
                {
                    "id": "bill_123",
                    "externalId": "contribution-1",
                    "url": "https://app.abacatepay.com/pay/bill_123",
                    "amount": 5000,
                    "paidAmount": None,
                    "status": "PENDING",
                }
            ],
        }
    )
    provider = AbacatePayPaymentProvider(api_key="test-key", http_client=http)

    checkout = provider.find_checkout("contribution-1")

    assert checkout.id == "bill_123"
    assert checkout.status == "PENDING"
    assert http.requests == [
        (
            "GET",
            "https://api.abacatepay.com/v2/checkouts/list?externalId=contribution-1&limit=1",
            {"Authorization": "Bearer test-key"},
            None,
        )
    ]
