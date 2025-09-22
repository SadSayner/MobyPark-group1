class Payment_model:
    def __init__(self, transaction_id, amount, initiator, created_at, completed, hash,
                 t_amount, t_date, t_method, t_issuer, t_bank):
        self.transaction_id = transaction_id
        self.amount = amount
        self.initiator = initiator
        self.created_at = created_at
        self.completed = completed
        self.hash = hash
        self.t_amount = t_amount
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
            initiator=data["initiator"],
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
            "initiator": self.initiator,
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
    return f"Payment_model(transaction_id={self.transaction_id}, amount={self.amount}, initiator={self.initiator}, created_at={self.created_at}, completed={self.completed}, hash={self.hash}, t_amount={self.t_amount}, t_date={self.t_date}, t_method={self.t_method}, t_issuer={self.t_issuer}, t_bank={self.t_bank})"
