from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import insert

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
    password_param = {
        "current_password": "password12345",
        "new_password": "new_secure_password123",
    }
    response = await authenticated_client.patch(
        "/users/me/password", json=password_param
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
        f"/users/{new_user_id}/role", json={"role": "Manager"}
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

    response = await authenticated_client.delete(f"/users/{new_user_id}")
    assert response.status_code == 204

    check = await authenticated_client.get(f"/users/{new_user_id}")
    assert check.status_code == 404


async def test_get_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/users/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_delete_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.delete("/users/999999")

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
        "/users/1/role",
        json={"role": "admin"},
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
        "/users/1", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403


async def test_deactivate_user_success(authenticated_client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="user_to_deact",
                email="deact@booking.com",
                password_hash="fakehash",
                role="user",
                is_active=True,
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.patch(f"/users/deactivate/{new_user_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == f"User {new_user_id} deactivated"


async def test_deactivate_admin_forbidden(
    authenticated_client: AsyncClient, db_session
):
    admin_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="admin_to_deact",
                email="admin_deact@booking.com",
                password_hash="fakehash",
                role="admin",
                is_active=True,
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.patch(f"/users/deactivate/{admin_id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot deactivate admin"


async def test_deactivate_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.patch("/users/deactivate/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_activate_user_success(authenticated_client: AsyncClient, db_session):
    new_user_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="user_to_act",
                email="act@booking.com",
                password_hash="fakehash",
                role="user",
                is_active=False,
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.patch(f"/users/activate/{new_user_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == f"User {new_user_id} activated"


async def test_activate_admin_forbidden(authenticated_client: AsyncClient, db_session):
    admin_id = (
        await db_session.execute(
            insert(Users)
            .values(
                username="admin_to_act",
                email="admin_act@booking.com",
                password_hash="fakehash",
                role="admin",
                is_active=False,
            )
            .returning(Users.id)
        )
    ).scalar()
    await db_session.commit()

    response = await authenticated_client.patch(f"/users/activate/{admin_id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot activate admin"


async def test_activate_user_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.patch("/users/activate/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
