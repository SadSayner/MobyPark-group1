class Vehicle_model:
    def __init__(self, id, user_id, license_plate, make, model, color, year, created_at):
        self.id = id
        self.user_id = user_id
        self.license_plate = license_plate
        self.make = make
        self.model = model
        self.color = color
        self.year = year
        self.created_at = created_at

    @staticmethod
    def from_dict(data):
        return Vehicle_model(
            id=data['id'],
            user_id=data['user_id'],
            license_plate=data['license_plate'],
            make=data['make'],
            model=data['model'],
            color=data['color'],
            year=data['year'],
            created_at=data['created_at']
        )
