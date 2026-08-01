import base64
import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from gamewake.billing import (
    Billing,
    ContributionPackage,
    ContributionStatus,
    InMemoryBillingRepository,
    InsufficientFundsError,
    LedgerEntryType,
    PaymentCheckout,
)
from gamewake.billing.abacatepay import AbacatePayWebhookHandler


class FakePaymentProvider:
    def __init__(self):
        self.requests = []
        self.refunds = []

    def create_checkout(self, request):
        self.requests.append(request)
        return PaymentCheckout(
            id="bill_123",
            external_id=request.external_id,
            url="https://app.abacatepay.com/pay/bill_123",
            amount=request.expected_amount,
        )

    def refund_checkout(self, checkout_id, *, reason):
        self.refunds.append((checkout_id, reason))
        return "tran_refund_123"

    def find_checkout(self, external_id):
        return None


def test_membership_starts_an_idempotent_wallet_contribution_checkout():
    provider = FakePaymentProvider()
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=provider,
        contribution_packages=(
            ContributionPackage(
                id="credit-50",
                amount=Decimal("50.00"),
                provider_product_id="prod_50_brl",
            ),
        ),
    )

    contribution = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )
    repeated = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )

    assert repeated == contribution
    assert contribution.status is ContributionStatus.PENDING
    assert contribution.amount == Decimal("50.00")
    assert contribution.payer_user_id == "user-1"
    assert contribution.provider_checkout_id == "bill_123"
    assert contribution.checkout_url == "https://app.abacatepay.com/pay/bill_123"
    assert len(provider.requests) == 1
    assert provider.requests[0].external_id == contribution.id
    assert provider.requests[0].provider_product_id == "prod_50_brl"


def test_completed_webhook_credits_the_wallet_exactly_once_when_replayed():
    provider = FakePaymentProvider()
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=provider,
        contribution_packages=(ContributionPackage("credit-50", Decimal("50.00"), "prod_50_brl"),),
    )
    contribution = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )
    payload = {
        "id": "log_completed_1",
        "event": "checkout.completed",
        "apiVersion": 2,
        "data": {
            "checkout": {
                "id": "bill_123",
                "externalId": contribution.id,
                "amount": 5000,
                "paidAmount": 5000,
                "status": "PAID",
                "methods": ["CARD"],
            },
            "payerInformation": {
                "method": "CARD",
                "CARD": {"number": "4242", "brand": "VISA"},
            },
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    hmac_key = "public-hmac-key"
    signature = base64.b64encode(
        hmac.new(hmac_key.encode(), raw_body, hashlib.sha256).digest()
    ).decode()
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key=hmac_key,
        event_processor=billing.process_payment_event,
    )

    first = handler.handle(
        raw_body,
        webhook_secret="url-secret",
        signature=signature,
    )
    repeated = handler.handle(
        raw_body,
        webhook_secret="url-secret",
        signature=signature,
    )

    wallet = billing.get_wallet("account-1")
    stored = billing.get_contribution(
        "account-1",
        contribution.id,
        requesting_user_id="user-1",
    )
    assert repeated == first
    assert stored.status is ContributionStatus.COMPLETED
    assert wallet.balance == Decimal("50.00")
    assert len(wallet.statement) == 1
    assert wallet.statement[0].reference == contribution.id
    assert stored.payment_method.method == "CARD"
    assert stored.payment_method.card_last_four == "4242"
    assert stored.payment_method.card_brand == "VISA"

    shared_view = billing.get_contribution(
        "account-1",
        contribution.id,
        requesting_user_id="user-2",
    )
    assert shared_view.payment_method is None
    assert shared_view.checkout_url is None


@pytest.mark.parametrize(
    ("event_type", "expected_status", "expected_ledger_type"),
    [
        ("checkout.refunded", ContributionStatus.REFUNDED, LedgerEntryType.REFUND),
        ("checkout.disputed", ContributionStatus.DISPUTED, LedgerEntryType.DISPUTE),
    ],
)
def test_refund_and_dispute_webhooks_append_exactly_one_compensating_entry(
    event_type,
    expected_status,
    expected_ledger_type,
):
    provider = FakePaymentProvider()
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=provider,
        contribution_packages=(ContributionPackage("credit-50", Decimal("50.00"), "prod_50_brl"),),
    )
    contribution = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=billing.process_payment_event,
    )
    _deliver(
        handler,
        _checkout_event("log_completed_1", "checkout.completed", contribution.id),
    )
    adjustment = _checkout_event("log_adjustment_1", event_type, contribution.id)

    first = _deliver(handler, adjustment)
    repeated = _deliver(handler, adjustment)

    wallet = billing.get_wallet("account-1")
    stored = billing.get_contribution(
        "account-1",
        contribution.id,
        requesting_user_id="user-1",
    )
    assert repeated == first
    assert stored.status is expected_status
    assert wallet.balance == Decimal("0.00")
    assert [entry.entry_type for entry in wallet.statement] == [
        LedgerEntryType.CONTRIBUTION,
        expected_ledger_type,
    ]
    assert [entry.amount for entry in wallet.statement] == [
        Decimal("50.00"),
        Decimal("-50.00"),
    ]


def test_payer_can_request_only_an_integral_refund_of_unspent_credit():
    provider = FakePaymentProvider()
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=provider,
        contribution_packages=(ContributionPackage("credit-50", Decimal("50.00"), "prod_50_brl"),),
    )
    contribution = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=billing.process_payment_event,
    )
    _deliver(
        handler,
        _checkout_event("log_completed_1", "checkout.completed", contribution.id),
    )

    requested = billing.request_contribution_refund(
        "account-1",
        contribution.id,
        requesting_user_id="user-1",
        reason="Créditos não utilizados",
    )
    repeated = billing.request_contribution_refund(
        "account-1",
        contribution.id,
        requesting_user_id="user-1",
        reason="Créditos não utilizados",
    )

    assert repeated == requested
    assert requested.status is ContributionStatus.REFUND_REQUESTED
    assert requested.provider_refund_id == "tran_refund_123"
    assert provider.refunds == [("bill_123", "Créditos não utilizados")]
    assert billing.get_wallet("account-1").balance == Decimal("50.00")


def test_provider_reversal_with_committed_credit_freezes_funding_without_negative_wallet():
    provider = FakePaymentProvider()
    billing = Billing(
        InMemoryBillingRepository(),
        payment_provider=provider,
        contribution_packages=(ContributionPackage("credit-50", Decimal("50.00"), "prod_50_brl"),),
    )
    contribution = billing.create_contribution(
        "account-1",
        payer_user_id="user-1",
        package_id="credit-50",
        return_url="https://gamewake.example/wallet",
        completion_url="https://gamewake.example/wallet/success",
        idempotency_key="checkout-command-1",
    )
    handler = AbacatePayWebhookHandler(
        webhook_secret="url-secret",
        public_hmac_key="public-hmac-key",
        event_processor=billing.process_payment_event,
    )
    _deliver(
        handler,
        _checkout_event("log_completed_1", "checkout.completed", contribution.id),
    )
    billing.reserve(
        "account-1",
        amount=Decimal("40.00"),
        purpose="wake:world-1",
        idempotency_key="wake-1",
    )

    _deliver(
        handler,
        _checkout_event("log_dispute_1", "checkout.disputed", contribution.id),
    )

    wallet = billing.get_wallet("account-1")
    stored = billing.get_contribution(
        "account-1",
        contribution.id,
        requesting_user_id="user-1",
    )
    assert stored.status is ContributionStatus.NEEDS_REVIEW
    assert wallet.balance == Decimal("50.00")
    assert wallet.available_balance == Decimal("0.00")
    assert len(wallet.statement) == 1
    with pytest.raises(InsufficientFundsError):
        billing.reserve(
            "account-1",
            amount=Decimal("0.01"),
            purpose="wake:world-2",
            idempotency_key="wake-2",
        )


def test_reconciliation_recovers_a_checkout_after_the_create_response_was_lost():
    class RecoveringProvider(FakePaymentProvider):
        def __init__(self):
            super().__init__()
            self.recovered_checkout = None

        def create_checkout(self, request):
            self.requests.append(request)
            raise RuntimeError("connection lost after provider accepted request")

        def find_checkout(self, external_id):
            return self.recovered_checkout

    repository = InMemoryBillingRepository()
    provider = RecoveringProvider()
    billing = Billing(
        repository,
        payment_provider=provider,
        contribution_packages=(ContributionPackage("credit-50", Decimal("50.00"), "prod_50_brl"),),
    )
    with pytest.raises(RuntimeError):
        billing.create_contribution(
            "account-1",
            payer_user_id="user-1",
            package_id="credit-50",
            return_url="https://gamewake.example/wallet",
            completion_url="https://gamewake.example/wallet/success",
            idempotency_key="checkout-command-1",
        )
    intent = repository.get("account-1").contributions[0]
    provider.recovered_checkout = PaymentCheckout(
        id="bill_recovered",
        external_id=intent.id,
        url="https://app.abacatepay.com/pay/bill_recovered",
        amount=Decimal("50.00"),
        status="PENDING",
    )

    recovered = billing.reconcile_contribution("account-1", intent.id)

    assert recovered.status is ContributionStatus.PENDING
    assert recovered.provider_checkout_id == "bill_recovered"
    assert recovered.checkout_url == "https://app.abacatepay.com/pay/bill_recovered"


def _checkout_event(event_id, event_type, contribution_id):
    return {
        "id": event_id,
        "event": event_type,
        "apiVersion": 2,
        "data": {
            "checkout": {
                "id": "bill_123",
                "externalId": contribution_id,
                "amount": 5000,
                "paidAmount": 5000,
                "status": "PAID",
                "methods": ["PIX"],
            },
            "payerInformation": {"method": "PIX"},
        },
    }


def _deliver(handler, payload):
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    signature = base64.b64encode(
        hmac.new(b"public-hmac-key", raw_body, hashlib.sha256).digest()
    ).decode()
    return handler.handle(
        raw_body,
        webhook_secret="url-secret",
        signature=signature,
    )
