from database_logic import get_all_parking_lots
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from storage_utils import *  # noqa

connection = get_connection()
vehicles = get_all_vehicles(connection)
vehicle_license_plate_dict = {}
for vehicle in vehicles:
    if vehicle.license_plate not in vehicle_license_plate_dict:
        vehicle_license_plate_dict[vehicle.license_plate] = 1
    else:
        vehicle_license_plate_dict[vehicle.license_plate] += 1

users = []

for license_plate, count in vehicle_license_plate_dict.items():
    if count > 1:
        print(
            f"Duplicate license plate found: {license_plate} appears {count} times.")
        for vehicle in get_vehicles_by_license_plate(connection, license_plate):
            users.append(vehicle.user_id)

for user in users:
    print(get_user_by_id(connection, user))
    print()
