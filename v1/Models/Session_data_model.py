class Session_data:
    def __init__(self, session_id, parking_lot_id, vehicle_id,
                 started, user_id, duration_minutes, payment_status):
        self.session_id = session_id
        self.parking_lot_id = parking_lot_id
        self.vehicle_id = vehicle_id
        self.started = started
        self.user_id = user_id
        self.duration_minutes = duration_minutes
        self.payment_status = payment_status

    @staticmethod
    def from_dict(data: dict) -> "Session_data":
        return Session_data(
            session_id=data.get("session_id", data.get(
                "id")),   # ✅ fallback to old "id"
            parking_lot_id=data["parking_lot_id"],
            vehicle_id=data["licenseplate"],
            started=data["started"],
            stopped=data.get("stopped"),
            user_id=data.get("user"),
            duration_minutes=data.get("duration_minutes"),
            payment_status=data.get("payment_status", "unpaid")
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, Session_data):
            return False
        return (
            self.session_id == other.session_id
            and self.parking_lot_id == other.parking_lot_id
            and self.vehicle_id == other.vehicle_id
            and self.started == other.started
            and self.user_id == other.user_id
            and self.duration_minutes == other.duration_minutes
            and self.payment_status == other.payment_status
        )

    def __repr__(self):
        return (f"Session_data(session_id={self.session_id}, parking_lot_id={self.parking_lot_id}, "
                f"licenseplate={self.licenseplate}, started={self.started}, stopped={self.stopped}, "
                f"user={self.user}, duration_minutes={self.duration_minutes}, cost={self.cost}, "
                f"payment_status={self.payment_status})")
