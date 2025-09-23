from database_logic import get_all_parking_lots
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from storage_utils import *  # noqa
from Models.user_model import *  # noqa

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
        for vehicle in get_vehicles_by_license_plate(connection, license_plate):
            users.append(vehicle.user_id)

user_models = []
for user in users:
    user_models.append(get_user_by_id(connection, user))

print(User_model.format_table(user_models))

# for user in user_models:
#     print(user)

# print(user_models)
# print(User_model.format_table([]))


# print(_line(User_model))
