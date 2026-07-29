import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.models.role_model import Role
from app.models.user_model import Users


async def seed_data() -> None:
    async with AsyncSessionLocal() as session:
        print("⏳ Starting database seeding...")

        users_to_seed = [
            ("admin", "admin@booking.com", Role.admin, settings.ADMIN_DEFAULT_PASSWORD),
            (
                "manager",
                "manager@booking.com",
                Role.manager,
                settings.MANAGER_DEFAULT_PASSWORD,
            ),
            ("user", "user@booking.com", Role.user, settings.USER_DEFAULT_PASSWORD),
        ]

        for username, email, role, password in users_to_seed:
            result = await session.execute(
                select(Users).where(Users.username == username)
            )
            user = result.scalar_one_or_none()

            if not user:
                print(f"Creating user '{username}'...")
                new_user = Users(
                    username=username,
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=True,
                )
                session.add(new_user)
            else:
                print(f"✅ User '{username}' already exists.")

        await session.commit()
        print("🎉 Database successfully seeded!")


if __name__ == "__main__":
    asyncio.run(seed_data())
