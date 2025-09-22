class User_model:
    def __init__(self, id, username, password, name, email, phone, role, created_at, birth_year, active):
        self.id = id
        self.username = username
        self.password = password
        self.name = name
        self.email = email
        self.phone = phone
        self.role = role
        self.created_at = created_at
        self.birth_year = birth_year
        self.active = active

    @staticmethod
    def from_dict(data):
        return User_model(
            id=data['id'],
            username=data['username'],
            password=data['password'],
            name=data['name'],
            email=data['email'],
            phone=data['phone'],
            role=data['role'],
            created_at=data['created_at'],
            birth_year=data['birth_year'],
            active=data['active']
        )

    def __repr__(self):
        # Define column widths
        widths = [20, 20, 35, 22, 15, 10, 15, 12, 10]
        headers = ["id", "username", "email", "name", "phone",
                   "role", "created_at", "birth_year", "active"]
        values = [
            str(self.id), self.username, self.email, self.name, self.phone,
            self.role, str(self.created_at), str(
                self.birth_year), str(self.active)
        ]

        # Build the horizontal line
        line = "+" + "+".join("-" * w for w in widths) + "+"

        # Build the header row
        header_row = "| " + \
            " | ".join(f"{h:<{w-2}}" for h, w in zip(headers, widths)) + " |"

        # Build the value row
        value_row = "| " + \
            " | ".join(f"{v:<{w-2}}" for v, w in zip(values, widths)) + " |"

        # Combine all parts
        return f"{line}\n{header_row}\n{line}\n{value_row}\n{line}"
