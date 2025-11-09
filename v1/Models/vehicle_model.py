class Vehicle_model:
    def __init__(self, id, license_plate, make, model, color, year, created_at):
        self.id = id
        self.license_plate = license_plate
        self.make = make
        self.model = model
        self.color = color
        self.year = year
        self.created_at = created_at

    def __repr__(self):
        return f"Vehicle_model(id={self.id},  license_plate={self.license_plate}, make={self.make}, model={self.model}, color={self.color}, year={self.year}, created_at={self.created_at})"
