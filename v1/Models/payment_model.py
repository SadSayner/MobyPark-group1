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

    @staticmethod
    def from_dict(data: dict):
        t_data = data.get("t_data", {})
        return Payment_model(
            # keep accepting external 'transaction'
            transaction_id=data["transaction"],
            amount=data["amount"],
            user_id=data["initiator"],
            created_at=data["created_at"],
            completed=data.get("completed"),
            hash=data["hash"],
            t_amount=t_data.get("amount"),
            t_date=t_data.get("date"),
            t_method=t_data.get("method"),
            t_issuer=t_data.get("issuer"),
            t_bank=t_data.get("bank")
        )

    def to_dict(self) -> dict:
        # IMPORTANT: use transaction_id to match DB schema
        return {
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "initiator": self.user_id,
            "created_at": self.created_at,
            "completed": self.completed,
            "hash": self.hash,
            "t_amount": self.t_amount,
            "t_date": self.t_date,
            "t_method": self.t_method,
            "t_issuer": self.t_issuer,
            "t_bank": self.t_bank,
        }


def __repr__(self):
    return f"Payment_model(transaction_id={self.transaction_id}, amount={self.amount}, initiator={self.user_id}, created_at={self.created_at}, completed={self.completed}, hash={self.hash}, t_amount={self.t_amount}, t_date={self.t_date}, t_method={self.t_method}, t_issuer={self.t_issuer}, t_bank={self.t_bank})"
