import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from hashlib import md5
import uuid

from v2.unittests.session_calculator import (
    calculate_price,
    generate_payment_hash,
    generate_transaction_validation_hash,
    check_payment_amount,
)


class TestPaymentUtils(unittest.TestCase):

    def test_calculate_price_under_3_minutes(self):
        parkinglot = {"tariff": 2.0, "daytariff": 10.0}
        start = (datetime.now() - timedelta(seconds=100)).strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start}
        result = calculate_price(parkinglot, "session1", data)
        self.assertEqual(result[0], 0)  # price
        self.assertEqual(result[1], 1)  # hours
        self.assertEqual(result[2], 0)  # days

    def test_calculate_price_same_day(self):
        parkinglot = {"tariff": 2.5, "daytariff": 20.0}
        start = (datetime.now() - timedelta(hours=3, minutes=10)).strftime(
            "%d-%m-%Y %H:%M:%S"
        )
        stop = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start, "stopped": stop}
        result = calculate_price(parkinglot, "sid1", data)
        self.assertEqual(result[0], 2.5 * 4)
        self.assertEqual(result[1], 4)
        self.assertEqual(result[2], 0)

    def test_calculate_price_exceeds_daytariff(self):
        parkinglot = {"tariff": 10.0, "daytariff": 15.0}
        start = (datetime.now() - timedelta(hours=4)).strftime("%d-%m-%Y %H:%M:%S")
        stop = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start, "stopped": stop}
        result = calculate_price(parkinglot, "sid1", data)
        self.assertEqual(result[0], 15.0)

    def test_calculate_price_multiple_days(self):
        parkinglot = {"tariff": 5.0, "daytariff": 20.0}
        start = (datetime.now() - timedelta(days=2, hours=5)).strftime(
            "%d-%m-%Y %H:%M:%S"
        )
        stop = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start, "stopped": stop}
        result = calculate_price(parkinglot, "sid1", data)
        self.assertEqual(result[0], 20.0 * 3)

    def test_generate_payment_hash(self):
        sid = "ABC123"
        data = {"licenseplate": "XYZ999"}
        expected = md5("ABC123XYZ999".encode("utf-8")).hexdigest()
        result = generate_payment_hash(sid, data)
        self.assertEqual(result, expected)

    def test_generate_transaction_validation_hash_unique(self):
        h1 = generate_transaction_validation_hash()
        h2 = generate_transaction_validation_hash()
        self.assertNotEqual(h1, h2)

        uuid.UUID(h1)
        uuid.UUID(h2)

    @patch("v2.unittests.session_calculator.load_payment_data")
    def test_check_payment_amount_found(self, mock_load):
        mock_load.return_value = [
            {"transaction": "hash1", "amount": 5},
            {"transaction": "hash2", "amount": 10},
            {"transaction": "hash1", "amount": 2.5},
        ]
        result = check_payment_amount("hash1")
        self.assertEqual(result, 7.5)

    @patch("v2.unittests.session_calculator.load_payment_data")
    def test_check_payment_amount_not_found(self, mock_load):
        mock_load.return_value = [{"transaction": "other", "amount": 99}]
        result = check_payment_amount("not_found")
        self.assertEqual(result, 0)

    def test_calculate_price_rounding_up_hour(self):
        """Check if partial hour is charged as full hour."""
        parkinglot = {"tariff": 2.0, "daytariff": 20.0}
        start = (datetime.now() - timedelta(hours=1, minutes=1)).strftime(
            "%d-%m-%Y %H:%M:%S"
        )
        stop = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start, "stopped": stop}
        result = calculate_price(parkinglot, "session_round", data)
        self.assertEqual(result[1], 2)

    def test_calculate_price_exact_day_bound(self):
        """Exactly 24 hours should count as 1 day."""
        parkinglot = {"tariff": 2.5, "daytariff": 10}
        start = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y %H:%M:%S")
        stop = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start, "stopped": stop}
        result = calculate_price(parkinglot, "d1", data)
        self.assertEqual(result[2], 1)
        self.assertEqual(result[0], 10)

    def test_calculate_price_missing_stopped_key(self):
        """If no stop time exists, it assumes ongoing parking."""
        parkinglot = {"tariff": 3.0, "daytariff": 30.0}
        start = (datetime.now() - timedelta(hours=2)).strftime("%d-%m-%Y %H:%M:%S")
        data = {"started": start}
        result = calculate_price(parkinglot, "sid_missing_stop", data)
        self.assertGreater(result[1], 1)

    def test_generate_payment_hash_missing_license_plate(self):
        """If no license plate exists, ensure function does not error."""
        sid = "UUID123"
        data = {}
        expected = md5("UUID123".encode("utf-8")).hexdigest()
        result = generate_payment_hash(sid, data)
        self.assertEqual(result, expected)

    def test_generate_transaction_validation_hash_format(self):
        """Ensure validation hash looks like UUID."""
        h = generate_transaction_validation_hash()
        try:
            uuid_obj = uuid.UUID(h)
        except Exception:
            self.fail(f"{h} is not a valid UUID format")

    @patch("v2.unittests.session_calculator.load_payment_data")
    def test_check_payment_amount_float_precision(self, mock_load):
        """Ensure summation works with float rounding."""
        mock_load.return_value = [
            {"transaction": "x1", "amount": 0.1},
            {"transaction": "x1", "amount": 0.2},
        ]
        result = check_payment_amount("x1")
        self.assertAlmostEqual(result, 0.3, places=2)

    @patch("v2.unittests.session_calculator.load_payment_data")
    def test_check_payment_amount_empty_list(self, mock_load):
        """No payments → should return 0."""
        mock_load.return_value = []
        result = check_payment_amount("xxx")
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
