class Session_data:
    def __init__(self, id, parking_lot_id, licenseplate, started, stopped, user, duration_minutes, cost, payment_status):
        self.id = id
        self.parking_lot_id = parking_lot_id
        self.licenseplate = licenseplate
        self.started = started
        self.stopped = stopped
        self.user = user
        self.duration_minutes = duration_minutes
        self.cost = cost
        self.payment_status = payment_status

    @staticmethod
    def from_dict(data):
        return Session_data(
            id=data['id'],
            parking_lot_id=data['parking_lot_id'],
            licenseplate=data['licenseplate'],
            started=data['started'],
            stopped=data['stopped'],
            user=data['user'],
            duration_minutes=data['duration_minutes'],
            cost=data['cost'],
            payment_status=data['payment_status']
        )

    def __eq__(self, other):
        if not isinstance(other, Session_data):
            return False
        return self.id == other.id and self.parking_lot_id == other.parking_lot_id and self.licenseplate == other.licenseplate and self.started == other.started and self.stopped == other.stopped and self.user == other.user and self.duration_minutes == other.duration_minutes and self.cost == other.cost and self.payment_status == other.payment_status
