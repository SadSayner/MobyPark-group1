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

    @staticmethod
    def from_dict(data):
        # Handle both nested coordinates and flat lat/lng
        if 'coordinates' in data:
            lat = data['coordinates']['lat']
            lng = data['coordinates']['lng']
        else:
            lat = data['lat']
            lng = data['lng']

        return Parking_lots_model(
            id=data['id'],
            name=data['name'],
            location=data['location'],
            address=data['address'],
            capacity=data['capacity'],
            reserved=data['reserved'],
            tariff=data['tariff'],
            daytariff=data['daytariff'],
            created_at=data['created_at'],
            lat=lat,
            lng=lng
        )

    def to_dict(self):
        """Convert this parking lot object to a dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'address': self.address,
            'capacity': self.capacity,
            'reserved': self.reserved,
            'tariff': self.tariff,
            'daytariff': self.daytariff,
            'created_at': self.created_at,
            'lat': self.lat,
            'lng': self.lng
        }

    def __repr__(self):
        return f"Parking_lots_model(id={self.id}, name={self.name}, location={self.location}, address={self.address}, capacity={self.capacity}, reserved={self.reserved}, tariff={self.tariff}, daytariff={self.daytariff}, created_at={self.created_at}, lat={self.lat}, lng={self.lng})"
