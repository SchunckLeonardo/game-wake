import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import ContributionCheckoutRequest, PaymentCheckout

_DEFAULT_BASE_URL = "https://api.abacatepay.com/v2"
_ABACATEPAY_USER_AGENT = "GameWake/0.1.0 (+https://gamewake.com.br)"


class PaymentProviderError(RuntimeError):
    """Raised when AbacatePay rejects or returns an invalid payment operation."""


class InvalidWebhookSignature(ValueError):
    """Raised before parsing a webhook that fails either authentication layer."""


class InvalidWebhookPayload(ValueError):
    """Raised after authentication when an AbacatePay event cannot be processed."""


class JsonHttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]: ...


class UrllibJsonHttpClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        request = Request(
            url,
            data=(json.dumps(json_body).encode("utf-8") if json_body is not None else None),
            headers={**headers, "User-Agent": _ABACATEPAY_USER_AGENT},
            method=method,
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            provider_message = self._http_error_message(error)
            raise PaymentProviderError(
                f"AbacatePay request failed ({error.code}): {provider_message}"
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise PaymentProviderError("AbacatePay request failed") from error
        if not isinstance(result, dict):
            raise PaymentProviderError("AbacatePay returned an invalid response")
        return result

    @staticmethod
    def _http_error_message(error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "provider rejected the request"
        message = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(message, str) or not message.strip():
            return "provider rejected the request"
        return message.strip()[:300]


class AbacatePayPaymentProvider:
    def __init__(
        self,
        *,
        api_key: str,
        http_client: JsonHttpClient | None = None,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        if not api_key:
            raise ValueError("AbacatePay API key is required")
        self._api_key = api_key
        self._http_client = http_client or UrllibJsonHttpClient()
        self._base_url = base_url.rstrip("/")

    def create_checkout(self, request: ContributionCheckoutRequest) -> PaymentCheckout:
        customer_id = self._create_customer(request)
        checkout_body: dict[str, Any] = {
            "items": [{"id": request.provider_product_id, "quantity": 1}],
            "methods": ["PIX"],
            "externalId": request.external_id,
            "returnUrl": request.return_url,
            "completionUrl": request.completion_url,
            "metadata": {"gamewakeContributionId": request.external_id},
        }
        if customer_id is not None:
            checkout_body["customerId"] = customer_id
        response = self._http_client.request(
            "POST",
            f"{self._base_url}/checkouts/create",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json_body=checkout_body,
        )
        if response.get("success") is not True or not isinstance(response.get("data"), dict):
            raise PaymentProviderError(str(response.get("error") or "checkout creation failed"))
        checkout = self._parse_checkout(response["data"])
        if checkout.external_id != request.external_id:
            raise PaymentProviderError("AbacatePay checkout externalId does not match")
        if checkout.amount != request.expected_amount:
            raise PaymentProviderError("AbacatePay checkout amount does not match credit package")
        return checkout

    def _create_customer(self, request: ContributionCheckoutRequest) -> str | None:
        email = request.payer_email.strip() if request.payer_email else ""
        if not email:
            return None
        customer_body: dict[str, Any] = {
            "email": email,
            "metadata": {"gamewakeContributionId": request.external_id},
        }
        if request.payer_name and request.payer_name.strip():
            customer_body["name"] = request.payer_name.strip()
        response = self._http_client.request(
            "POST",
            f"{self._base_url}/customers/create",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json_body=customer_body,
        )
        data = response.get("data")
        if response.get("success") is not True or not isinstance(data, dict):
            raise PaymentProviderError(str(response.get("error") or "customer creation failed"))
        customer_id = data.get("id")
        if not isinstance(customer_id, str) or not customer_id.startswith("cust_"):
            raise PaymentProviderError("AbacatePay returned an invalid customer")
        return customer_id

    def find_checkout(self, external_id: str) -> PaymentCheckout | None:
        query = urlencode({"externalId": external_id, "limit": 1})
        response = self._http_client.request(
            "GET",
            f"{self._base_url}/checkouts/list?{query}",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json_body=None,
        )
        data = response.get("data")
        if response.get("success") is not True or not isinstance(data, list):
            raise PaymentProviderError(str(response.get("error") or "checkout lookup failed"))
        matching = [
            item
            for item in data
            if isinstance(item, dict) and item.get("externalId") == external_id
        ]
        if not matching:
            return None
        checkout = self._parse_checkout(matching[0])
        if checkout.external_id != external_id:
            raise PaymentProviderError("AbacatePay checkout externalId does not match")
        return checkout

    def refund_checkout(self, checkout_id: str, *, reason: str) -> str:
        if not checkout_id.startswith("bill_"):
            raise ValueError("AbacatePay Checkout ID must start with bill_")
        if not reason or len(reason) > 500:
            raise ValueError("refund reason must contain between 1 and 500 characters")
        response = self._http_client.request(
            "POST",
            f"{self._base_url}/checkouts/refund",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json_body={"id": checkout_id, "reason": reason},
        )
        if response.get("success") is not True or not isinstance(response.get("data"), dict):
            raise PaymentProviderError(str(response.get("error") or "checkout refund failed"))
        refund_id = response["data"].get("refundPublicId")
        if not isinstance(refund_id, str) or not refund_id:
            raise PaymentProviderError("AbacatePay returned an invalid refund")
        return refund_id

    @staticmethod
    def _parse_checkout(data: Mapping[str, Any]) -> PaymentCheckout:
        try:
            amount = Decimal(int(data["amount"])) / Decimal(100)
            paid_cents = data.get("paidAmount")
            paid_amount = (
                Decimal(int(paid_cents)) / Decimal(100) if paid_cents is not None else None
            )
            return PaymentCheckout(
                id=str(data["id"]),
                external_id=str(data["externalId"]),
                url=str(data["url"]),
                amount=amount,
                status=str(data["status"]),
                paid_amount=paid_amount,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PaymentProviderError("AbacatePay returned an invalid checkout") from error


class AbacatePayWebhookHandler:
    def __init__(
        self,
        *,
        webhook_secret: str,
        public_hmac_key: str,
        event_processor: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        if not webhook_secret or not public_hmac_key:
            raise ValueError("AbacatePay webhook secrets are required")
        self._webhook_secret = webhook_secret
        self._public_hmac_key = public_hmac_key
        self._event_processor = event_processor

    def handle(self, raw_body: bytes, *, webhook_secret: str, signature: str) -> Any:
        expected_signature = base64.b64encode(
            hmac.new(
                self._public_hmac_key.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        if not hmac.compare_digest(self._webhook_secret, webhook_secret) or not hmac.compare_digest(
            expected_signature,
            signature,
        ):
            raise InvalidWebhookSignature("invalid AbacatePay webhook authentication")
        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidWebhookPayload("invalid AbacatePay webhook JSON") from error
        if not isinstance(payload, dict):
            raise InvalidWebhookPayload("invalid AbacatePay webhook payload")
        try:
            return self._event_processor(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidWebhookPayload("invalid AbacatePay webhook event") from error
