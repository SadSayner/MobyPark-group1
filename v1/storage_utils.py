# storage_utils.py
import sqlite3
import csv
import json
from database_logic import *
from Models.Session_data_model import Session_data
from Models.parkinglots_model import parking_lots_model


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


data = load_data('v1\data\pdata\p1-sessions.json')
parking_lots = load_data('v1\data\parking-lots.json')

for entry_key, entry_value in parking_lots.items():
    insert_parking_lot(
        get_connection('v1\MobyPark.db'), parking_lots_model.from_dict(entry_value))
