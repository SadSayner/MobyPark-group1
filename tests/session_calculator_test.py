from hashlib import md5
import math
import uuid
from datetime import datetime
from v1 import session_calculator as sc

def test_calculate_price():
    parkinglot = {"tariff": 2.5, "daytariff": 20}

    # Test case 1: Duration less than 3 minutes (free)
    data = {"started": "01-01-2025 10:00:00", "stopped": "01-01-2025 10:02:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid1", data)
    assert price == 0   
    assert hours == 1
    assert days == 0

    # Test case 2: Duration of 2 hours on the same day
    data = {"started": "01-01-2024 10:00:00 ", "stopped": "01-01-2024 12:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid2", data)
    assert price == 5.0
    assert hours == 2
    assert days == 0           

    # Test case 3: Duration exceeding day tariff    
    data = {"started": "01-01-2024 10:00:00", "stopped": "01-01-2024 20:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid3", data)
    assert price == 20.0         
    assert hours == 10
    assert days == 1

    # Test case 4: Duration spanning multiple days
    data = {"started": "01-01-2024 10:00:00", "stopped": "03-01-2024 12:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid4", data)
    assert price == 60.0
    assert hours == 26
    assert days == 3

    # Test case 5: Ongoing session (no stopped time)
    data = {"started": "01-01-2024 10:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid5", data)
    assert price >= 0
    assert hours >= 0
    assert days >= 0

    # Test case 6: Day pass usage
    data = {"started": "01-01-2024 10:00:00", "stopped": "01-01-2024 12:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid6", data)
    assert price == 5.0
    assert hours == 2
    assert days == 0

    # Day passes 
    data = {"started": "01-01-2024 10:00:00", "stopped": "02-01-2024 12:00:00"}
    price, hours, days = sc.calculate_price(parkinglot, "sid7", data)
    assert price == 20.0
    assert hours == 26
    assert days == 2

    