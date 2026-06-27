from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.models.user_model import Users

router = APIRouter(tags=["Users"])


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(user: Annotated[Users, Depends(get_current_user)]):
    return user