# storage_utils.py
import sqlite3
import csv
import json
from Database.database_logic import *
from Models.Session_data_model import Session_data
from Models.parkinglots_model import Parking_lots_model
from Models.reservations_model import Reservations_model
from Models.user_model import User_model
from Models.vehicle_model import Vehicle_model
import datetime


def load_json(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def write_json(filename, data):
    with open(filename, 'w') as file:
        json.dump(data, file, default=str)


def load_csv(filename):
    try:
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            return [row for row in reader]
    except FileNotFoundError:
        return []


def write_csv(filename, data):
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        for row in data:
            writer.writerow(row)


def load_text(filename):
    try:
        with open(filename, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        return []


def write_text(filename, data):
    with open(filename, 'w') as file:
        for line in data:
            file.write(line + '\n')


def write_log(message):
    filename = datetime.datetime.now().strftime("log_%Y-%m-%d.txt")
    with open(filename, 'a') as file:
        file.write(message + '\n')


def save_data(filename, data):
    if filename.endswith('.json'):
        write_json(filename, data)
    elif filename.endswith('.csv'):
        write_csv(filename, data)
    elif filename.endswith('.txt'):
        write_text(filename, data)
    else:
        raise ValueError("Unsupported file format")


def load_data(filename):
    if filename.endswith('.json'):
        return load_json(filename)
    elif filename.endswith('.csv'):
        return load_csv(filename)
    elif filename.endswith('.txt'):
        return load_text(filename)
    else:
        return None


def load_user_data():
    return load_data('data/users.json')


def save_user_data(data):
    save_data('data/users.json', data)


def load_parking_lot_data():
    return load_data('data/parking-lots.json')


def save_parking_lot_data(data):
    save_data('data/parking-lots.json', data)


def load_reservation_data():
    return load_data('data/reservations.json')


def save_reservation_data(data):
    save_data('data/reservations.json', data)


def load_payment_data():
    return load_data('data/payments.json')


def save_payment_data(data):
    save_data('data/payments.json', data)


def load_discounts_data():
    return load_data('data/discounts.csv')


def save_discounts_data(data):
    save_data('data/discounts.csv', data)


connection = get_connection('v1\Database\MobyPark.db')


def get_parking_lot_data_from_json():
    return load_data('v1\data\parking-lots.json')


def get_user_data_from_json():
    return load_data("v1//data//users.json")


def get_vehicle_data_from_json():
    return load_data('v1\data//vehicles.json')


def get_reservation_data_from_json():
    return load_data('v1\data//reservations.json')


def add_parking_lots_to_db():
    connection = get_connection()
    parking_lots = get_parking_lot_data_from_json()
    logs = []
    for entry_value in parking_lots.values():
        if not record_exists(connection, 'parking_lots', Parking_lots_model.to_dict(entry_value)):
            insert_parking_lot(
                connection, Parking_lots_model.from_dict(entry_value))
        else:
            log_message = f"Parking lot with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log('\n'.join(logs))


def add_users_to_db():
    connection = get_connection()
    users = get_user_data_from_json()
    logs = []
    for entry_value in users:
        if not record_exists(connection, 'users', entry_value):
            insert_user(
                connection, User_model.from_dict(entry_value))
        else:
            log_message = f"User with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log('\n'.join(logs))


def add_vehicles_to_db():
    connection = get_connection()
    vehicles = get_vehicle_data_from_json()
    logs = []
    for entry_value in vehicles:
        if not record_exists(connection, 'vehicles', entry_value):
            insert_vehicle(
                connection, Vehicle_model.from_dict(entry_value))
        else:
            log_message = f"Vehicle with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log('\n'.join(logs))


def add_reservations_to_db():
    connection = get_connection()
    reservations = get_reservation_data_from_json()
    logs = []
    for entry_value in reservations:
        if not record_exists(connection, 'reservations', entry_value):
            insert_reservation(
                connection, Reservations_model.from_dict(entry_value))
        else:
            log_message = f"Reservation with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log('\n'.join(logs))


def add_session_data_to_db():
    connection = get_connection()
    sessions = load_data('v1\data\pdata\p2-sessions.json')
    logs = []
    for entry_value in sessions.values():
        if not record_exists(connection, 'parking_sessions', entry_value):
            insert_parking_session(
                connection, Session_data.from_dict(entry_value))
        else:
            log_message = f"Session with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log('\n'.join(logs))


def main():
    add_session_data_to_db()
    # add_parking_lots_to_db()
    # add_users_to_db()
    # add_vehicles_to_db()
    # add_reservations_to_db()


if __name__ == "__main__":
    main()
