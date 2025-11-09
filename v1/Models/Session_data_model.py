class Session_data:
    def __init__(self, session_id, parking_lot_id, user_id,
                 started, duration, payment_status):
        self.session_id = session_id
        self.parking_lot_id = parking_lot_id
        self.user_id = user_id
        self.started = started
        self.duration = duration
        self.payment_status = payment_status

    def __repr__(self):
        return (f"Session_data(session_id={self.session_id}, parking_lot_id={self.parking_lot_id}, "
                f"started={self.started}, duration={self.duration}, "
                f"user={self.user}, duration={self.duration}, cost={self.cost}, "
                f"payment_status={self.payment_status})")
