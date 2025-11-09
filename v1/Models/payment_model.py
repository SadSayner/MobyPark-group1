class Payment_model:
    def __init__(self, payment_id, transaction, amount, user_id, session_id, parking_lot_id, created_at, completed, hash, t_date, t_method, t_issuer, t_bank):
        self.payment_id = payment_id
        self.transaction = transaction
        self.amount = amount
        self.user_id = user_id
        self.session_id = session_id
        self.parking_lot_id = parking_lot_id
        self.created_at = created_at
        self.completed = completed
        self.hash = hash
        self.t_date = t_date
        self.t_method = t_method
        self.t_issuer = t_issuer
        self.t_bank = t_bank

    def __repr__(self):
        return f"Payment_model(transaction_id={self.transaction_id}, amount={self.amount}, initiator={self.user_id}, created_at={self.created_at}, completed={self.completed}, hash={self.hash}, t_amount={self.t_amount}, t_date={self.t_date}, t_method={self.t_method}, t_issuer={self.t_issuer}, t_bank={self.t_bank})"

    @staticmethod
    def from_dict(**content):
        try:
            return Payment_model(
                payment_id=content.get("payment_id"),
                transaction=content.get("transaction"),
                amount=content.get("amount"),
                user_id=content.get("user_id"),
                session_id=content.get("session_id"),
                parking_lot_id=content.get("parking_lot_id"),
                created_at=content.get("created_at"),
                completed=content.get("completed"),
                hash=content.get("hash"),
                t_date=content.get("t_date"),
                t_method=content.get("t_method"),
                t_issuer=content.get("t_issuer"),
                t_bank=content.get("t_bank"),
            )
        except KeyError as e:
            raise ValueError(f"Missing key in content dict: {e}")
