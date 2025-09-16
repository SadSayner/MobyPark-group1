class parking_lots_model:
    def __init__(self, id, name, location, address, capacity, reserved, tariff, daytariff, created_at, coordinates):
        self.id = id
        self.name = name
        self.location = location
        self.address = address
        self.capacity = capacity
        self.reserved = reserved
        self.tariff = tariff
        self.daytariff = daytariff
        self.created_at = created_at
        self.coordinates = coordinates

    @staticmethod
    def from_dict(data):
        return parking_lots_model(
            id=data['id'],
            name=data['name'],
            location=data['location'],
            address=data['address'],
            capacity=data['capacity'],
            reserved=data['reserved'],
            tariff=data['tariff'],
            daytariff=data['daytariff'],
            created_at=data['created_at'],
            coordinates=data['coordinates']
        )
