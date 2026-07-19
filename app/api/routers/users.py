from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete

from app.api.dependencies import DbSession
from app.api.dependencies import allow_admin_and_manager, allow_admin, get_current_user
from app.models.user_model import Users
from app.models.role_model import Role
from app.core.security import hash_password
from app.schemas.user_schema import UserOut, UserPasswordUpdate, UserRoleUpdate


router = APIRouter(tags=["Users"])


@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserOut)
async def get_my_info(user: Annotated[Users, Depends(get_current_user)]) -> UserOut:
    return user


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    db: DbSession,
    password_data: UserPasswordUpdate,
    user: Annotated[Users, Depends(get_current_user)],
) -> dict[str, str]:
    new_hashed_password = hash_password(password_data.new_password)
    await db.execute(
        update(Users)
        .filter(Users.id == user.id)
        .values(password_hash=new_hashed_password)
    )
    await db.commit()
    return {"status": "success"}


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=list[UserOut],
)
async def get_all_users(db: DbSession) -> list[UserOut]:
    query_result = await db.execute(select(Users))
    users = query_result.scalars().all()
    return users


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=UserOut,
)
async def get_user_info(db: DbSession, user_id: int) -> UserOut:
    user = await db.execute(select(Users).filter(Users.id == user_id))
    result_user = user.scalars().first()

    if not result_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return result_user


@router.patch(
    "/{user_id}/role",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin)],
)
async def change_role(
    role_data: UserRoleUpdate, user_id: int, db: DbSession
) -> dict[str, str]:
    user_to_change = await db.execute(select(Users).filter(Users.id == user_id))
    user = user_to_change.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.role == Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change admin role",
        )

    await db.execute(
        update(Users).filter(Users.id == user_id).values(role=role_data.role)
    )
    await db.commit()
    return {"status": "success"}


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_admin)],
)
async def delete_user(db: DbSession, user_id: int) -> None:
    user_to_delete = await db.execute(select(Users).filter(Users.id == user_id))
    user = user_to_delete.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.role == Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete admin",
        )

    await db.execute(delete(Users).filter(Users.id == user_id).returning(Users.id))
    await db.commit()


@router.patch(
    "/deactivate/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin)],
)
async def deactivate_user(db: DbSession, user_id: int) -> dict[str, str]:
    user_to_deactivate = await db.execute(select(Users).filter(Users.id == user_id))
    user = user_to_deactivate.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.role == Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate admin",
        )

    result = await db.execute(
        update(Users)
        .filter(Users.id == user_id)
        .values(is_active=False)
        .returning(Users.id)
    )

    updated_user_id = result.scalar_one_or_none()

    if not updated_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await db.commit()
    return {"status": "success", "message": f"User {user_id} deactivated"}


@router.patch(
    "/activate/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin)],
)
async def activate_user(db: DbSession, user_id: int) -> dict[str, str]:
    user_to_activate = await db.execute(select(Users).filter(Users.id == user_id))
    user = user_to_activate.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.role == Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot activate admin",
        )

    result = await db.execute(
        update(Users)
        .filter(Users.id == user_id)
        .values(is_active=True)
        .returning(Users.id)
    )

    updated_user_id = result.scalar_one_or_none()

    if not updated_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await db.commit()
    return {"status": "success", "message": f"User {user_id} activated"}
