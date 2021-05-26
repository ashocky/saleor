import json
from unittest.mock import Mock, patch

import pytest
from stripe.stripe_object import StripeObject

from .....checkout.complete_checkout import complete_checkout
from .... import ChargeStatus, TransactionKind
from ....utils import price_to_minor_unit
from ..consts import (
    AUTHORIZED_STATUS,
    FAILED_STATUSES,
    PROCESSING_STATUS,
    SUCCESS_STATUS,
    WEBHOOK_AUTHORIZED_EVENT,
    WEBHOOK_CANCELED_EVENT,
    WEBHOOK_FAILED_EVENT,
    WEBHOOK_PROCESSING_EVENT,
    WEBHOOK_SUCCESS_EVENT,
)
from ..webhooks import (
    handle_authorized_payment_intent,
    handle_failed_payment_intent,
    handle_processing_payment_intent,
    handle_successful_payment_intent,
)


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_successful_payment_intent_for_checkout(
    wrapped_checkout_complete,
    payment_stripe_for_checkout,
    checkout_with_items,
    stripe_plugin,
):
    payment = payment_stripe_for_checkout
    payment.to_confirm = True
    payment.save()
    payment.transactions.create(
        is_success=True,
        action_required=True,
        kind=TransactionKind.ACTION_TO_CONFIRM,
        amount=payment.total,
        currency=payment.currency,
        token="ABC",
        gateway_response={},
    )
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = price_to_minor_unit(payment.total, payment.currency)
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = SUCCESS_STATUS
    handle_successful_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert wrapped_checkout_complete.called
    assert payment.checkout_id is None
    assert payment.order
    assert payment.order.checkout_token == str(checkout_with_items.token)
    transaction = payment.transactions.get(kind=TransactionKind.CAPTURE)
    assert transaction.token == payment_intent.id


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_successful_payment_intent_for_order(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    stripe_plugin,
):

    payment = payment_stripe_for_order
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["capture_method"] = "automatic"
    handle_successful_payment_intent(payment_intent, plugin.config)

    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_successful_payment_intent_for_order_with_auth_payment(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    stripe_plugin,
):
    payment = payment_stripe_for_order

    plugin = stripe_plugin()

    payment_intent = StripeObject(id="token", last_response={})
    payment_intent["amount"] = price_to_minor_unit(payment.total, payment.currency)
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = SUCCESS_STATUS

    handle_successful_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert payment.is_active
    assert payment.charge_status == ChargeStatus.FULLY_CHARGED
    assert payment.captured_amount == payment.total
    assert payment.transactions.filter(kind=TransactionKind.CAPTURE).exists()
    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_successful_payment_intent_for_order_with_pending_payment(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    stripe_plugin,
):
    payment = payment_stripe_for_order
    transaction = payment.transactions.first()
    transaction.kind = TransactionKind.PENDING
    transaction.save()

    plugin = stripe_plugin()

    payment_intent = StripeObject(id="token", last_response={})
    payment_intent["amount"] = price_to_minor_unit(payment.total, payment.currency)
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = SUCCESS_STATUS

    handle_successful_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert payment.is_active
    assert payment.charge_status == ChargeStatus.FULLY_CHARGED
    assert payment.captured_amount == payment.total
    assert payment.transactions.filter(kind=TransactionKind.CAPTURE).exists()
    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_authorized_payment_intent_for_checkout(
    wrapped_checkout_complete,
    payment_stripe_for_checkout,
    checkout_with_items,
    stripe_plugin,
):
    payment = payment_stripe_for_checkout
    payment.to_confirm = True
    payment.save()
    payment.transactions.create(
        is_success=True,
        action_required=True,
        kind=TransactionKind.ACTION_TO_CONFIRM,
        amount=payment.total,
        currency=payment.currency,
        token="ABC",
        gateway_response={},
    )
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = price_to_minor_unit(payment.total, payment.currency)
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = AUTHORIZED_STATUS
    handle_authorized_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert wrapped_checkout_complete.called
    assert payment.checkout_id is None
    assert payment.order
    assert payment.order.checkout_token == str(checkout_with_items.token)
    transaction = payment.transactions.get(kind=TransactionKind.AUTH)
    assert transaction.token == payment_intent.id


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_authorized_payment_intent_for_order(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    checkout_with_items,
    stripe_plugin,
):

    payment = payment_stripe_for_order
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = AUTHORIZED_STATUS
    handle_authorized_payment_intent(payment_intent, plugin.config)

    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_authorized_payment_intent_for_processing_order_payment(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    checkout_with_items,
    stripe_plugin,
):

    payment = payment_stripe_for_order
    payment.charge_status = ChargeStatus.PENDING
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = AUTHORIZED_STATUS
    handle_authorized_payment_intent(payment_intent, plugin.config)

    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_processing_payment_intent_for_order(
    wrapped_checkout_complete,
    payment_stripe_for_order,
    checkout_with_items,
    stripe_plugin,
):

    payment = payment_stripe_for_order
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = PROCESSING_STATUS
    handle_processing_payment_intent(payment_intent, plugin.config)

    assert wrapped_checkout_complete.called is False


@patch(
    "saleor.payment.gateways.stripe.webhooks.complete_checkout", wraps=complete_checkout
)
def test_handle_processing_payment_intent_for_checkout(
    wrapped_checkout_complete,
    payment_stripe_for_checkout,
    checkout_with_items,
    stripe_plugin,
):
    payment = payment_stripe_for_checkout
    payment.to_confirm = True
    payment.save()
    payment.transactions.create(
        is_success=True,
        action_required=True,
        kind=TransactionKind.ACTION_TO_CONFIRM,
        amount=payment.total,
        currency=payment.currency,
        token="ABC",
        gateway_response={},
    )
    plugin = stripe_plugin()
    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = price_to_minor_unit(payment.total, payment.currency)
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = PROCESSING_STATUS
    handle_processing_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert wrapped_checkout_complete.called
    assert payment.checkout_id is None
    assert payment.order
    assert payment.order.checkout_token == str(checkout_with_items.token)
    transaction = payment.transactions.get(kind=TransactionKind.PENDING)
    assert transaction.token == payment_intent.id


def test_handle_failed_payment_intent_for_checkout(
    stripe_plugin, payment_stripe_for_checkout
):
    payment = payment_stripe_for_checkout
    payment.transactions.create(
        is_success=True,
        action_required=True,
        kind=TransactionKind.ACTION_TO_CONFIRM,
        amount=payment.total,
        currency=payment.currency,
        token="ABC",
        gateway_response={},
    )

    plugin = stripe_plugin()

    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = FAILED_STATUSES[0]

    handle_failed_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert not payment.order_id
    assert not payment.is_active
    assert payment.charge_status == ChargeStatus.CANCELLED
    assert payment.transactions.filter(kind=TransactionKind.CANCEL).exists()


def test_handle_failed_payment_intent_for_order(
    stripe_plugin, payment_stripe_for_order
):
    payment = payment_stripe_for_order
    payment.transactions.create(
        is_success=True,
        action_required=True,
        kind=TransactionKind.ACTION_TO_CONFIRM,
        amount=payment.total,
        currency=payment.currency,
        token="ABC",
        gateway_response={},
    )

    plugin = stripe_plugin()

    payment_intent = StripeObject(id="ABC", last_response={})
    payment_intent["amount"] = payment.total
    payment_intent["currency"] = payment.currency
    payment_intent["status"] = FAILED_STATUSES[0]

    handle_failed_payment_intent(payment_intent, plugin.config)

    payment.refresh_from_db()

    assert not payment.is_active
    assert payment.charge_status == ChargeStatus.CANCELLED
    assert payment.transactions.filter(kind=TransactionKind.CANCEL).exists()


@pytest.mark.parametrize(
    "webhook_type, fun_to_mock",
    [
        (WEBHOOK_SUCCESS_EVENT, "handle_successful_payment_intent"),
        (WEBHOOK_PROCESSING_EVENT, "handle_processing_payment_intent"),
        (WEBHOOK_FAILED_EVENT, "handle_failed_payment_intent"),
        (WEBHOOK_AUTHORIZED_EVENT, "handle_authorized_payment_intent"),
        (WEBHOOK_CANCELED_EVENT, "handle_failed_payment_intent"),
    ],
)
@patch("saleor.payment.gateways.stripe.stripe_api.stripe.Webhook.construct_event")
def test_handle_webhook_successful_payment_intent(
    mocked_webhook_event, webhook_type, fun_to_mock, stripe_plugin, rf
):
    dummy_payload = {
        "id": "evt_1Ip9ANH1Vac4G4dbE9ch7zGS",
    }

    request = rf.post(
        path="/webhooks/", data=dummy_payload, content_type="application/json"
    )

    stripe_signature = "1234"
    request.META["HTTP_STRIPE_SIGNATURE"] = stripe_signature

    event = Mock()
    event.type = webhook_type
    event.data.object = StripeObject()

    mocked_webhook_event.return_value = event

    plugin = stripe_plugin()

    with patch(f"saleor.payment.gateways.stripe.webhooks.{fun_to_mock}") as mocked_fun:
        plugin.webhook(request, "/webhooks/", None)
        mocked_fun.assert_called_once_with(event.data.object, plugin.config)

    api_key = plugin.config.connection_params["secret_api_key"]
    endpoint_secret = plugin.config.connection_params["webhook_secret"]

    mocked_webhook_event.assert_called_once_with(
        json.dumps(dummy_payload).encode("utf-8"),
        stripe_signature,
        endpoint_secret,
        api_key=api_key,
    )