"""JWT 认证：登录接口和令牌校验依赖。"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])
_security = HTTPBearer()

_SECRET = os.environ["JWT_SECRET"]
_ALGORITHM = "HS256"
_EXPIRE_DAYS = 7  # token 有效期（天），如需调整直接修改此常量


class LoginRequest(BaseModel):
    username: str
    password: str


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """校验 Bearer token，返回用户名。其他路由通过 Depends(verify_token) 使用。"""
    try:
        payload = jwt.decode(credentials.credentials, _SECRET, algorithms=[_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")


@router.post("/login")
def login(body: LoginRequest):
    """用户名 + 密码登录，返回 JWT access_token。"""
    if body.username != os.environ["AUTH_USERNAME"] or body.password != os.environ["AUTH_PASSWORD"]:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    expire = datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS)
    token = jwt.encode({"sub": body.username, "exp": expire}, _SECRET, algorithm=_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}
