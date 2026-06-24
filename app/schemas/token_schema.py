from pydantic import BaseModel


class RefreshToken_Schema(BaseModel):
    refresh_token: str