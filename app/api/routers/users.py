from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete

from app.api.dependencies import DbSession
from app.api.dependencies import allow_admin_and_manager, allow_admin, get_current_user
from app.models.role_model import Role
from app.models.user_model import Users

router = APIRouter(tags=["Users"])


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(user: Annotated[Users, Depends(get_current_user)]):
    return user


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
        db: DbSession,
        new_password: str,
        user: Annotated[Users, Depends(get_current_user)]
):
    await db.execute(update(Users).filter(Users.id == user.id).values(password_hash=new_password))
    await db.commit()
    return {"status": "success"}


@router.get("/", status_code=status.HTTP_200_OK, dependencies=[Depends(allow_admin_and_manager)])
async def get_all_users(db: DbSession):
    query_result = await db.execute(select(Users))
    users = query_result.scalars().all()
    return users



@router.get("/{user_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(allow_admin_and_manager)])
async def get_user_info(db: DbSession, user_id: int):
    user = await db.execute(select(Users).filter(Users.id == user_id))
    result_user = user.scalars().first()

    if not result_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return result_user


@router.patch("/{role}", status_code=status.HTTP_200_OK, dependencies=[Depends(allow_admin)])
async def change_role(new_role: Role, id: int, db: DbSession):
    await db.execute(update(Users).filter(Users.id == id).values(role=new_role))
    await db.commit()
    return {"status": "success"}


@router.delete("/remove/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
async def delete_user(db: DbSession, id: int):
    user_to_delete = await db.execute(delete(Users).filter(Users.id == id).returning(Users.id))
    result = user_to_delete.scalars().first()

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.commit()