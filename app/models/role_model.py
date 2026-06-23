import enum

class Role(str, enum.Enum):
    user = "User"
    manager = "Manager"
    admin = "Admin"
