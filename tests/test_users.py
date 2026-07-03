from httpx import AsyncClient
from sqlalchemy import insert
from datetime import timedelta
from app.core.security import create_access_token
from app.models.user_model import Users


async def test_get_user_me(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/users/me")
    assert response.status_code == 200
    assert response.json()["username"].startswith("tester_")


async def test_get_all_users(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


async def test_get_user_by_id(authenticated_client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="TestPerson",
                email="test_person@example.com",
                password_hash="securepassword123",
                role="user",
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.get(f"/users/{new_user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "TestPerson"


async def test_change_password(authenticated_client: AsyncClient):
    password_param = {"new_password": "new_secure_password123"}
    response = await authenticated_client.patch(
        "/users/me/password", params=password_param
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_change_user_role(authenticated_client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="role_user",
                email="role@example.com",
                password_hash="hash",
                role="user",
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.patch(
        "/users/manager", params={"id": new_user_id, "new_role": "Manager"}
    )

    assert response.status_code == 200


async def test_delete_user_by_admin(authenticated_client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="to_delete",
                email="delete@me.com",
                password_hash="hash",
                role="user",
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.delete(f"/users/remove/{new_user_id}")
    assert response.status_code == 204

    check = await authenticated_client.get(f"/users/{new_user_id}")
    assert check.status_code == 404


async def test_get_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/users/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_delete_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.delete("/users/remove/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_change_user_role_forbidden(client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="normal_user",
                email="normal@example.com",
                password_hash="hash",
                role="user",
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    user_token = create_access_token({"sub": str(new_user_id)}, timedelta(minutes=5))

    response = await client.patch(
        "/users/manager",
        params={"id": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 403


async def test_delete_user_forbidden(client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="another_user",
                email="another@example.com",
                password_hash="hash",
                role="user",
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    user_token = create_access_token({"sub": str(new_user_id)}, timedelta(minutes=5))

    response = await client.delete(
        "/users/remove/1", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403
