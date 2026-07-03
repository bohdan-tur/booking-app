import asyncio
from sqlalchemy import select
from passlib.context import CryptContext


from app.db.database import AsyncSessionLocal

from app.models.role_model import Role
from app.models.user_model import Users


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def seed_data():

    async with AsyncSessionLocal() as session:
        print("⏳ Starting database seeding...")

        # Admin user
        result = await session.execute(select(Users).where(Users.username == "admin"))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            print("Creating user 'admin'...")
            admin_user = Users(
                username="admin",
                email="admin@booking.com",
                password_hash=get_password_hash("AdminSecure123!"),
                role=Role.admin,
                is_active=True,
            )
            session.add(admin_user)
        else:
            print("✅ User 'admin' already exists.")

        # Manager user
        result = await session.execute(select(Users).where(Users.username == "manager"))
        manager_user = result.scalar_one_or_none()

        if not manager_user:
            print("Creating user 'manager'...")
            manager_user = Users(
                username="manager",
                email="manager@booking.com",
                password_hash=get_password_hash("ManagerSecure456!"),
                role=Role.manager,
                is_active=True,
            )
            session.add(manager_user)
        else:
            print("✅ User 'manager' already exists.")

        # Regular user
        result = await session.execute(select(Users).where(Users.username == "user"))
        regular_user = result.scalar_one_or_none()

        if not regular_user:
            print("Creating user 'user'...")
            regular_user = Users(
                username="user",
                email="user@booking.com",
                password_hash=get_password_hash("UserSecure789!"),
                role=Role.user,
                is_active=True,
            )
            session.add(regular_user)
        else:
            print("✅ User 'user' already exists.")

        await session.commit()
        print("🎉 Database successfully seeded! You can now login in Swagger.")


if __name__ == "__main__":
    asyncio.run(seed_data())
