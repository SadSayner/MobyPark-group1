class Reservations_model:
    def __init__(self, id, user_id, parking_lot_id, vehicle_id, start_time, duration, status, created_at):
        self.id = id
        self.user_id = user_id
        self.parking_lot_id = parking_lot_id
        self.vehicle_id = vehicle_id
        self.start_time = start_time
        self.duration = duration
        self.status = status
        self.created_at = created_at


def __repr__(self):
    return f"Reservations_model(id={self.id}, user_id={self.user_id}, parking_lot_id={self.parking_lot_id}, vehicle_id={self.vehicle_id}, start_time={self.start_time}, end_time={self.end_time}, status={self.status}, created_at={self.created_at}, cost={self.cost})"
