from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete

from app.dependencies import DbSession
from app.core.security import hash_password
from app.dependencies import allow_admin_and_manager, allow_admin, get_current_user
from app.models.role_model import Role
from app.models.user_model import Users
from app.schemas.user_schema import UserOut, UserCreate

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


@router.post("/new", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def add_user(user_data: UserCreate, db: DbSession):
    query_result = await db.execute(select(Users).filter(Users.email == user_data.email))

    if query_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    hashed_pwd = hash_password(user_data.password)
    new_user = Users(
        username=user_data.username,
        password_hash=hashed_pwd,
        email=user_data.email,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


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