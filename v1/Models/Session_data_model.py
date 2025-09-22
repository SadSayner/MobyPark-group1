class Session_data:
    def __init__(self, session_id, parking_lot_id, licenseplate,
                 started, stopped, user, duration_minutes, cost, payment_status):
        self.session_id = session_id
        self.parking_lot_id = parking_lot_id
        self.licenseplate = licenseplate
        self.started = started
        self.stopped = stopped
        self.user = user
        self.duration_minutes = duration_minutes
        self.cost = cost
        self.payment_status = payment_status

    @staticmethod
    def from_dict(data: dict) -> "Session_data":
        return Session_data(
            session_id=data.get("session_id", data.get(
                "id")),   # ✅ fallback to old "id"
            parking_lot_id=data["parking_lot_id"],
            licenseplate=data["licenseplate"],
            started=data["started"],
            stopped=data.get("stopped"),
            user=data.get("user"),
            duration_minutes=data.get("duration_minutes"),
            cost=data.get("cost"),
            payment_status=data.get("payment_status", "unpaid")
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, Session_data):
            return False
        return (
            self.session_id == other.session_id
            and self.parking_lot_id == other.parking_lot_id
            and self.licenseplate == other.licenseplate
            and self.started == other.started
            and self.stopped == other.stopped
            and self.user == other.user
            and self.duration_minutes == other.duration_minutes
            and self.cost == other.cost
            and self.payment_status == other.payment_status
        )

    def __repr__(self):
        return (f"Session_data(session_id={self.session_id}, parking_lot_id={self.parking_lot_id}, "
                f"licenseplate={self.licenseplate}, started={self.started}, stopped={self.stopped}, "
                f"user={self.user}, duration_minutes={self.duration_minutes}, cost={self.cost}, "
                f"payment_status={self.payment_status})")
