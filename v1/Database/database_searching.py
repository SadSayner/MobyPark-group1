from .database_logic import get_all_parking_lots
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..storage_utils import *  # noqa
from ..Models.user_model import *  # noqa

connection = get_connection()
parking_lots = get_all_parking_lots(connection)
print(parking_lots[0])
parking_lot = get_parking_lot_by_id(connection, 1)
print(parking_lot)