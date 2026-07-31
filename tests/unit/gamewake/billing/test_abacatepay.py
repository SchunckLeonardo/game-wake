import json
from decimal import Decimal

import pytest

from gamewake.billing import ContributionCheckoutRequest
from gamewake.billing.abacatepay import (
    AbacatePayPaymentProvider,
    AbacatePayWebhookHandler,
    InvalidWebhookSignature,
)


class RecordingHttpClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, url, *, headers, json_body=None):
        self.requests.append((method, url, headers, json_body))
        return self.response


def test_checkout_uses_the_configured_credit_product_and_pix_and_card():
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
                "methods": ["PIX", "CARD"],
                "externalId": "contribution-1",
                "returnUrl": "https://gamewake.example/wallet",
                "completionUrl": "https://gamewake.example/wallet/success",
                "metadata": {"gamewakeContributionId": "contribution-1"},
            },
        )
    ]


def test_webhook_rejects_an_invalid_signature_before_processing_the_event():
    processed = []
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=processed.append,
    )
    raw_body = json.dumps(
        {"id": "log_1", "event": "checkout.completed", "data": {}}
    ).encode()

    with pytest.raises(InvalidWebhookSignature):
        handler.handle(
            raw_body,
            webhook_secret="url-secret",
            signature="forged-signature",
        )

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
