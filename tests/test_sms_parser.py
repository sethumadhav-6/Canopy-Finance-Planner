from datetime import date

from core.sms_parser import is_likely_transaction_sms, parse_sms


def test_hdfc_style_debit():
    sms = ("Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl. "
           "UPI Ref 123456789012. Not you? Call 1800-xxx-xxxx")
    result = parse_sms(sms)
    assert result is not None
    assert result.txn_type == "expense"
    assert result.amount_major == 450.00
    assert result.txn_date == "2026-09-01"
    assert result.merchant == "officemart@ybl"
    assert result.account_hint == "1234"
    assert result.confidence > 0.7


def test_card_spend_style():
    sms = "INR 1,234.50 spent on your SBI Card ending 5678 at AMAZON on 02-Sep-26."
    result = parse_sms(sms)
    assert result is not None
    assert result.amount_major == 1234.50
    assert result.txn_type == "expense"
    assert result.txn_date == "2026-09-02"
    assert "amazon" in result.merchant.lower()


def test_credit_style():
    sms = "Your A/c XX9988 is credited with Rs.50000.00 on 01-09-2026 by NEFT from EMPLOYER LTD."
    result = parse_sms(sms)
    assert result is not None
    assert result.txn_type == "income"
    assert result.amount_major == 50000.00


def test_upi_sent_style():
    sms = "Sent Rs.200 to friend@okhdfcbank from your account via UPI on 03/09/2026."
    result = parse_sms(sms)
    assert result is not None
    assert result.txn_type == "expense"
    assert result.merchant == "friend@okhdfcbank"
    assert result.txn_date == "2026-09-03"


def test_otp_message_ignored():
    sms = "Your OTP for transaction of Rs.500 is 384921. Do not share this with anyone."
    assert parse_sms(sms) is None
    assert is_likely_transaction_sms(sms) is False


def test_promo_message_ignored():
    sms = "Get Rs.100 cashback on your next purchase! Offer valid till 30-Sep. Click here to know more."
    assert parse_sms(sms) is None


def test_bill_reminder_ignored():
    sms = "Your credit card bill of Rs.4500 is generated. Minimum due Rs.500. EMI due on 05-Sep-26."
    assert parse_sms(sms) is None


def test_no_amount_ignored():
    sms = "Your account balance is low. Please add funds to avoid transaction failures."
    assert parse_sms(sms) is None


def test_amount_but_no_direction_keyword_ignored():
    sms = "Your monthly statement for Rs.5000.00 is now available for A/c XX1234."
    assert parse_sms(sms) is None


def test_missing_date_falls_back_to_received_date():
    sms = "Rs.99 debited from A/c XX0001 to VPA shop@upi."
    result = parse_sms(sms, received_at=date(2026, 9, 15))
    assert result is not None
    assert result.txn_date == "2026-09-15"


def test_is_likely_transaction_sms_true_for_valid():
    sms = "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl."
    assert is_likely_transaction_sms(sms) is True


def test_empty_text():
    assert parse_sms("") is None
    assert parse_sms(None) is None


def test_merchant_at_pattern_without_vpa():
    sms = "Rs.780.00 spent at BIGBAZAAR on 04-09-26 using your debit card."
    result = parse_sms(sms)
    assert result is not None
    assert "bigbazaar" in result.merchant.lower()
