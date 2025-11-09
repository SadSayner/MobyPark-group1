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

    @staticmethod
    def from_dict(**content: dict):
        try:
            return Vehicle_model(
                id=content.get("id"),
                license_plate=content.get("license_plate"),
                make=content.get("make"),
                model=content.get("model"),
                color=content.get("color"),
                year=content.get("year"),
                created_at=content.get("created_at"),
            )
        except KeyError as e:
            raise ValueError(f"Missing key in content dict: {e}")
