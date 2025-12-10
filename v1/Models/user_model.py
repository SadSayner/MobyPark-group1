class User_model:

    _WIDTHS = [20, 20, 35, 22, 15, 10, 15, 12, 10]
    _HEADERS = ["id", "username", "email", "name", "phone",
                "role", "created_at", "birth_year", "active"]

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

    # --- helpers ---
    @classmethod
    def _line(cls):
        return "+" + "+".join("-" * w for w in cls._WIDTHS) + "+"

    @classmethod
    def _header_row(cls):
        return "| " + " | ".join(f"{h:<{w-2}}" for h, w in zip(cls._HEADERS, cls._WIDTHS)) + " |"

    def _values(self):
        return [
            str(self.id), self.username, self.email, self.name, self.phone,
            self.role, str(self.created_at), str(
                self.birth_year), str(self.active)
        ]

    def _row(self):
        return "| " + " | ".join(f"{v:<{w-2}}" for v, w in zip(self._values(), self._WIDTHS)) + " |"

    # --- key bits ---
    def __repr__(self):
        # Row-only: used when inside lists, dicts, etc.
        return self._row()

    def __str__(self):
        # Full table with header: used by print(user)
        line = self._line()
        header = self._header_row()
        return f"{line}\n{header}\n{line}\n{self._row()}\n{line}"

    @staticmethod
    def format_table(objects):
        line = User_model._line()
        header = User_model._header_row()
        if not objects:
            # Optional: a nice empty table
            return f"{line}\n{header}\n{line}\n{line}"
        rows = "\n".join(o._row() for o in objects)
        return f"{line}\n{header}\n{line}\n{rows}\n{line}"

    @staticmethod
    def from_dict(**content: dict):
        try:
            return User_model(
                id=content.get("id"),
                username=content.get("username"),
                password=content.get("password"),
                name=content.get("name"),
                email=content.get("email"),
                phone=content.get("phone"),
                role=content.get("role"),
                created_at=content.get("created_at"),
                birth_year=content.get("birth_year"),
                active=content.get("active"),
            )
        except KeyError as e:
            raise ValueError(f"Missing key in content dict: {e}")
