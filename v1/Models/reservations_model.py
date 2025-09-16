class reservations_model:
    def __init__(self, id, user_id, parking_lot_id, vehicle_id, start_time, end_time, status, created_at, cost):
        self.id = id
        self.user_id = user_id
        self.parking_lot_id = parking_lot_id
        self.vehicle_id = vehicle_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.created_at = created_at
        self.cost = cost

    @staticmethod
    def from_dict(data):
        return reservations_model(
            id=data['id'],
            user_id=data['user_id'],
            parking_lot_id=data['parking_lot_id'],
            vehicle_id=data['vehicle_id'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            status=data['status'],
            created_at=data['created_at'],
            cost=data['cost']
        )
