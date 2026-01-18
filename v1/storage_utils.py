# storage_utils.py
import sqlite3
import csv
import json
import os
import datetime
from .Database.database_logic import *
from .Models.Session_data_model import Session_data
from .Models.parkinglots_model import Parking_lots_model
from .Models.reservations_model import Reservations_model
from .Models.user_model import User_model
from .Models.vehicle_model import Vehicle_model
from .Models.payment_model import Payment_model


def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return []


def write_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, default=str)


def load_csv(filename):
    try:
        with open(filename, "r") as file:
            reader = csv.reader(file)
            return [row for row in reader]
    except FileNotFoundError:
        return []


def write_csv(filename, data):
    with open(filename, "w", newline="") as file:
        writer = csv.writer(file)
        for row in data:
            writer.writerow(row)


def load_text(filename):
    try:
        with open(filename, "r") as file:
            return file.readlines()
    except FileNotFoundError:
        return []


def write_text(filename, data):
    with open(filename, "w") as file:
        for line in data:
            file.write(line + "\n")


def write_log(message):
    filename = datetime.datetime.now().strftime("log_%Y-%m-%d.txt")
    with open(filename, "a") as file:
        file.write(message + "\n")


def save_data(filename, data):
    if filename.endswith(".json"):
        write_json(filename, data)
    elif filename.endswith(".csv"):
        write_csv(filename, data)
    elif filename.endswith(".txt"):
        write_text(filename, data)
    else:
        raise ValueError("Unsupported file format")


def load_data(filename):
    if filename.endswith(".json"):
        return load_json(filename)
    elif filename.endswith(".csv"):
        return load_csv(filename)
    elif filename.endswith(".txt"):
        return load_text(filename)
    else:
        return None


# Get the directory where this file is located
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")


def _get_data_path(filename):
    """Get absolute path to data file"""
    return os.path.join(_DATA_DIR, filename)


def load_user_data():
    return load_data(_get_data_path("users.json"))


def save_user_data(data):
    save_data(_get_data_path("users.json"), data)


def load_parking_lot_data():
    return load_data(_get_data_path("parking-lots.json"))


def save_parking_lot_data(data):
    save_data(_get_data_path("parking-lots.json"), data)


def load_reservation_data():
    return load_data(_get_data_path("reservations.json"))


def save_reservation_data(data):
    save_data(_get_data_path("reservations.json"), data)


def load_payment_data():
    return load_data(_get_data_path("payments.json"))


def save_payment_data(data):
    save_data(_get_data_path("payments.json"), data)


def load_discounts_data():
    return load_data(_get_data_path("discounts.csv"))


def save_discounts_data(data):
    save_data(_get_data_path("discounts.csv"), data)


def get_parking_lot_data_from_json():
    return load_data(_get_data_path("parking-lots.json"))


def get_user_data_from_json():
    return load_data(_get_data_path("users.json"))


def get_vehicle_data_from_json():
    return load_data(_get_data_path("vehicles.json"))


def get_reservation_data_from_json():
    return load_data(_get_data_path("reservations.json"))


def add_parking_lots_to_db():
    connection = get_connection()
    parking_lots = get_parking_lot_data_from_json()
    logs = []
    for entry_value in parking_lots.values():
        if not record_exists(
            connection, "parking_lots", Parking_lots_model.to_dict(entry_value)
        ):
            insert_parking_lot(
                connection, Parking_lots_model.from_dict(entry_value))
        else:
            log_message = f"Parking lot with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log("\n".join(logs))


def add_users_to_db():
    connection = get_connection()
    users = get_user_data_from_json()
    logs = []
    for entry_value in users:
        if not record_exists(connection, "users", entry_value):
            insert_user(connection, User_model.from_dict(entry_value))
        else:
            log_message = (
                f"User with ID {entry_value['id']} already exists. Skipping insertion."
            )
            logs.append(log_message)
    write_log("\n".join(logs))


def add_vehicles_to_db():
    connection = get_connection()
    vehicles = get_vehicle_data_from_json()
    logs = []
    for entry_value in vehicles:
        if not record_exists(connection, "vehicles", entry_value):
            insert_vehicle(connection, Vehicle_model.from_dict(entry_value))
        else:
            log_message = f"Vehicle with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log("\n".join(logs))


def add_reservations_to_db():
    connection = get_connection()
    reservations = get_reservation_data_from_json()
    logs = []
    for entry_value in reservations:
        if not record_exists(connection, "reservations", entry_value):
            insert_reservation(
                connection, Reservations_model.from_dict(entry_value))
        else:
            log_message = f"Reservation with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log("\n".join(logs))


def add_session_data_to_db():
    connection = get_connection()
    sessions_path = os.path.join(_DATA_DIR, "pdata", "p2-sessions.json")
    sessions = load_data(sessions_path)
    logs = []
    if not sessions:
        return  # Skip if no sessions file
    for entry_value in sessions.values():
        if not record_exists(connection, "sessions", entry_value):
            insert_parking_session(
                connection, Session_data.from_dict(entry_value))
        else:
            log_message = f"Session with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    if logs:
        write_log("\n".join(logs))


def add_payments_to_db():
    connection = get_connection()
    payments = load_data(_get_data_path("payments.json"))
    logs = []
    if not payments:
        return  # Skip if no payments file
    for entry_value in payments:
        transaction = Payment_model.to_dict(
            Payment_model.from_dict(entry_value))
        if not record_exists(connection, "payments", transaction):
            insert_payment(connection, Payment_model.from_dict(entry_value))
        else:
            log_message = f"Payment with ID {entry_value['id']} already exists. Skipping insertion."
            logs.append(log_message)
    write_log("\n".join(logs))


def main():
    """
    Main function to load all data from JSON files into the database.
    Run this after providing your JSON data files in v1/data/ directory.
    """
    print("Loading data from JSON files into database...")
    print(f"Data directory: {_DATA_DIR}")

    # Check if data directory exists
    if not os.path.exists(_DATA_DIR):
        print(f"Creating data directory: {_DATA_DIR}")
        os.makedirs(_DATA_DIR)
        print("Please add your JSON data files to the data/ directory and run again.")
        return

    # Load data into database
    try:
        add_parking_lots_to_db()
        print("- Parking lots loaded")
    except Exception as e:
        print(f"- Parking lots: {e}")

    try:
        add_users_to_db()
        print("- Users loaded")
    except Exception as e:
        print(f"- Users: {e}")

    try:
        add_vehicles_to_db()
        print("- Vehicles loaded")
    except Exception as e:
        print(f"- Vehicles: {e}")

    try:
        add_reservations_to_db()
        print("- Reservations loaded")
    except Exception as e:
        print(f"- Reservations: {e}")

    try:
        add_session_data_to_db()
        print("- Sessions loaded")
    except Exception as e:
        print(f"- Sessions: {e}")

    try:
        add_payments_to_db()
        print("- Payments loaded")
    except Exception as e:
        print(f"- Payments: {e}")

    print("\nData loading complete!")


if __name__ == "__main__":
    main()
