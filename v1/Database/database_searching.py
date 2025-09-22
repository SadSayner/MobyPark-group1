from database_logic import get_all_parking_lots
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage_utils import *  # noqa

connection = get_connection()
vehicles = get_all_vehicles(connection)
count = 0
for vehicle in vehicles:
    if len(vehicle.license_plate) >= 9:
        count += 1
print(f"Aantal voertuigen met een kenteken van 9 of meer tekens: {count}")
