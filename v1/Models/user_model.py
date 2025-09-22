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
        return f"User_model(id={self.id}, username={self.username}, password={self.password}, name={self.name}, email={self.email}, phone={self.phone}, role={self.role}, created_at={self.created_at}, birth_year={self.birth_year}, active={self.active})"
