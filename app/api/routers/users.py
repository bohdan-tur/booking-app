from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update

from app.api.dependencies import (
    DbSession,
    Pagination,
    allow_admin,
    allow_admin_and_manager,
    get_current_user,
)
from app.core.security import hash_password, verify_password
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserOut, UserPasswordUpdate, UserRoleUpdate
from app.services.refresh_token_service import RefreshTokenService

router = APIRouter(tags=["Users"])


@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserOut)
async def get_my_info(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return user


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    db: DbSession,
    password_data: UserPasswordUpdate,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(password_data.new_password)
    user.tokens_valid_after = datetime.now(UTC)
    await RefreshTokenService(db).revoke_all(user.id)
    return {"status": "success"}


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=list[UserOut],
)
async def get_all_users(db: DbSession, pagination: Pagination) -> list[UserOut]:
    query = (
        select(User).order_by(User.id).offset(pagination.offset).limit(pagination.limit)
    )
    query_result = await db.execute(query)
    return query_result.scalars().all()


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin_and_manager)],
    response_model=UserOut,
)
async def get_user_info(db: DbSession, user_id: int) -> UserOut:
    user = await db.execute(select(User).filter(User.id == user_id))
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
    user_to_change = await db.execute(select(User).filter(User.id == user_id))
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
        update(User).filter(User.id == user_id).values(role=role_data.role)
    )
    await db.commit()
    return {"status": "success"}


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_admin)],
)
async def delete_user(db: DbSession, user_id: int) -> None:
    user_to_delete = await db.execute(select(User).filter(User.id == user_id))
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

    await db.execute(delete(User).filter(User.id == user_id).returning(User.id))
    await db.commit()


@router.patch(
    "/deactivate/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(allow_admin)],
)
async def deactivate_user(db: DbSession, user_id: int) -> dict[str, str]:
    user_to_deactivate = await db.execute(select(User).filter(User.id == user_id))
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
        update(User)
        .filter(User.id == user_id)
        .values(is_active=False)
        .returning(User.id)
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
    user_to_activate = await db.execute(select(User).filter(User.id == user_id))
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
        update(User)
        .filter(User.id == user_id)
        .values(is_active=True)
        .returning(User.id)
    )

    updated_user_id = result.scalar_one_or_none()

    if not updated_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await db.commit()
    return {"status": "success", "message": f"User {user_id} activated"}
