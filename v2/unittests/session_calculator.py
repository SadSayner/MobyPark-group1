from datetime import datetime
from v2.unittests.storage_utils import load_payment_data
from hashlib import md5
import math
import uuid


def calculate_price(parkinglot, sid, data):
    price = 0
    start = datetime.strptime(data["started"], "%d-%m-%Y %H:%M:%S")

    if data.get("stopped"):
        end = datetime.strptime(data["stopped"], "%d-%m-%Y %H:%M:%S")
    else:
        end = datetime.now()

    diff = end - start
    hours = math.ceil(diff.total_seconds() / 3600)

    if diff.total_seconds() < 180:
        price = 0
    elif end.date() > start.date():
        price = float(parkinglot.get("daytariff", 999)) * (diff.days + 1)
    else:
        price = float(parkinglot.get("tariff")) * hours

        if price > float(parkinglot.get("daytariff", 999)):
            price = float(parkinglot.get("daytariff", 999))

    return (price, hours, diff.days + 1 if end.date() > start.date() else 0)


def generate_payment_hash(sid, data):
    return md5(str(sid + data["licenseplate"]).encode("utf-8")).hexdigest()


def generate_transaction_validation_hash():
    return str(uuid.uuid4())


def check_payment_amount(hash):
    payments = load_payment_data()
    total = 0

    for payment in payments:
        if payment["transaction"] == hash:
            total += payment["amount"]

    return total


import pytest
from unittest.mock import patch


@pytest.fixture
def parkinglot():
    return {"tariff": "5", "daytariff": "20"}


@pytest.fixture
def base_data():
    return {"licenseplate": "ABC123", "started": "01-01-2025 12:00:00"}


def test_price_free_under_three_minutes(parkinglot, base_data):
    base_data["stopped"] = "01-01-2025 12:02:59"
    price, hours, days = calculate_price(parkinglot, "SID1", base_data)
    assert price == 0
    assert hours == 1
    assert days == 0


def test_price_exact_three_minutes_charged(parkinglot, base_data):
    base_data["stopped"] = "01-01-2025 12:03:00"
    price, hours, days = calculate_price(parkinglot, "SID2", base_data)
    assert price == 5
    assert hours == 1
    assert days == 0


def test_hour_rounding_up(parkinglot, base_data):
    base_data["stopped"] = "01-01-2025 13:01:00"
    price, hours, _ = calculate_price(parkinglot, "SID3", base_data)
    assert hours == 2
    assert price == 10


def test_day_tariff_cap(parkinglot, base_data):
    base_data["stopped"] = "01-01-2025 17:00:00"
    price, hours, _ = calculate_price(parkinglot, "SID4", base_data)
    assert price == 20
    assert hours == 5


def test_multi_day_price(parkinglot, base_data):
    base_data["stopped"] = "03-01-2025 12:00:00"
    price, hours, days = calculate_price(parkinglot, "SID5", base_data)
    assert price == 60
    assert days == 3


@patch("datetime.datetime")
def test_no_stopped_uses_now(mock_datetime, parkinglot, base_data):
    mock_datetime.now.return_value = datetime(2025, 1, 1, 13, 0, 0)
    mock_datetime.strptime = datetime.strptime

    price, hours, _ = calculate_price(parkinglot, "SID6", base_data)
    assert price == 5
    assert hours == 1


def test_generate_payment_hash_consistent(base_data):
    first = generate_payment_hash("SIDX", base_data)
    second = generate_payment_hash("SIDX", base_data)
    assert first == second


def test_generate_payment_hash_changes_with_different_input(base_data):
    h1 = generate_payment_hash("SID", base_data)
    base_data["licenseplate"] = "ZZZ999"
    h2 = generate_payment_hash("SID", base_data)
    assert h1 != h2


def test_generate_payment_hash_length(base_data):
    assert len(generate_payment_hash("A", base_data)) == 32


def test_generate_transaction_validation_hash_valid():
    value = generate_transaction_validation_hash()
    assert len(value) == 36
    uuid.UUID(value)


def test_generate_transaction_validation_hash_unique():
    assert (
        generate_transaction_validation_hash() != generate_transaction_validation_hash()
    )


@patch("v2.unittests.storage_utils.load_payment_data")
def test_check_payment_amount_single(mock_load):
    mock_load.return_value = [{"transaction": "T1", "amount": 10}]
    assert check_payment_amount("T1") == 10


@patch("v2.unittests.storage_utils.load_payment_data")
def test_check_payment_amount_multiple(mock_load):
    mock_load.return_value = [
        {"transaction": "ABC", "amount": 5},
        {"transaction": "ABC", "amount": 15},
    ]
    assert check_payment_amount("ABC") == 20


@patch("v2.unittests.storage_utils.load_payment_data")
def test_check_payment_amount_no_match(mock_load):
    mock_load.return_value = []
    assert check_payment_amount("NONE") == 0
