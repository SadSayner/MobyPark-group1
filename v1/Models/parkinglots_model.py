class Parking_lots_model:
    def __init__(self, id, name, location, address, capacity, reserved, tariff, daytariff, created_at, lat, lng):
        self.id = id
        self.name = name
        self.location = location
        self.address = address
        self.capacity = capacity
        self.reserved = reserved
        self.tariff = tariff
        self.daytariff = daytariff
        self.created_at = created_at
        self.lat = lat
        self.lng = lng

    def __repr__(self):
        return f"Parking_lots_model(id={self.id}, name={self.name}, location={self.location}, address={self.address}, capacity={self.capacity}, reserved={self.reserved}, tariff={self.tariff}, daytariff={self.daytariff}, created_at={self.created_at}, lat={self.lat}, lng={self.lng})"

    @staticmethod
    def from_dict(**content: dict):
        try:
            return Parking_lots_model(
                id=content.get("id"),
                name=content.get("name"),
                location=content.get("location"),
                address=content.get("address"),
                capacity=content.get("capacity"),
                reserved=content.get("reserved"),
                tariff=content.get("tariff"),
                daytariff=content.get("daytariff"),
                created_at=content.get("created_at"),
                lat=content.get("lat"),
                lng=content.get("lng"),
            )
        except KeyError as e:
            raise ValueError(f"Missing key in content dict: {e}")
