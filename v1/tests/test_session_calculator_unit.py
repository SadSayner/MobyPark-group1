import uuid
from datetime import datetime
from hashlib import md5
from unittest.mock import patch

import pytest

from v1.session_calculator import (
    calculate_price,
    generate_payment_hash,
    generate_transaction_validation_hash,
    check_payment_amount,
)


class TestSessionCalculatorUnit:
    def test_calculate_price_under_3_minutes(self):
        pricing = {"tariff": 2.0, "daytariff": 10.0}
        data = {"started": "01-01-2025 10:00:00", "stopped": "01-01-2025 10:01:40"}  # 100s

        price, hours, days = calculate_price(pricing, "sid1", data)
        assert price == 0
        assert hours == 1
        assert days == 0

    def test_calculate_price_same_day_rounds_up_hours(self):
        pricing = {"tariff": 2.5, "daytariff": 20.0}
        data = {"started": "01-01-2025 10:00:00", "stopped": "01-01-2025 13:10:00"}  # 3h10m -> 4h

        price, hours, days = calculate_price(pricing, "sid2", data)
        assert hours == 4
        assert days == 0
        assert price == 2.5 * 4

    def test_calculate_price_exceeds_daytariff_caps(self):
        pricing = {"tariff": 10.0, "daytariff": 15.0}
        data = {"started": "01-01-2025 10:00:00", "stopped": "01-01-2025 14:00:00"}  # 4h

        price, hours, days = calculate_price(pricing, "sid3", data)
        assert hours == 4
        assert days == 0
        assert price == 15.0

    def test_calculate_price_multiple_days_uses_daytariff(self):
        pricing = {"tariff": 5.0, "daytariff": 20.0}
        data = {"started": "01-01-2025 10:00:00", "stopped": "03-01-2025 15:00:00"}  # spans 3 calendar days

        price, hours, days = calculate_price(pricing, "sid4", data)
        assert days == 3
        assert price == 20.0 * 3

    def test_generate_payment_hash(self):
        sid = "ABC123"
        data = {"licenseplate": "XYZ999"}
        expected = md5("ABC123XYZ999".encode("utf-8")).hexdigest()
        assert generate_payment_hash(sid, data) == expected

    def test_generate_transaction_validation_hash_is_uuid(self):
        h1 = generate_transaction_validation_hash()
        h2 = generate_transaction_validation_hash()

        assert h1 != h2
        uuid.UUID(h1)
        uuid.UUID(h2)

    @patch("v1.session_calculator.load_payment_data")
    def test_check_payment_amount_found(self, mock_load):
        mock_load.return_value = [
            {"transaction": "hash1", "amount": 5},
            {"transaction": "hash2", "amount": 10},
            {"transaction": "hash1", "amount": 2.5},
        ]

        assert check_payment_amount("hash1") == pytest.approx(7.5)

    @patch("v1.session_calculator.load_payment_data")
    def test_check_payment_amount_not_found(self, mock_load):
        mock_load.return_value = [{"transaction": "other", "amount": 99}]
        assert check_payment_amount("not_found") == 0
