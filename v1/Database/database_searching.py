from database_logic import get_all_parking_lots
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from storage_utils import *  # noqa
from Models.user_model import *  # noqa

connection = get_connection()

users = load_data("v1/data/users.json")
print(users[3417])
