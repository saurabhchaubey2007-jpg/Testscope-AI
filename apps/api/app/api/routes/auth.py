from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import (
    COOKIE_NAME, create_access_token, get_current_user, hash_password, verify_password,
)
from apps.api.app.models.user import User
from apps.api.app.schemas.user import TokenOut, UserCreate, UserLogin, UserOut, UserSettingsUpdate

router = APIRouter()


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name,
        has_github_token=bool(user.github_token), created_at=user.created_at,
        llm_provider=user.llm_provider or settings.default_llm_provider,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=TokenOut)
def register(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = User(email=email, name=payload.name, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    _set_auth_cookie(response, token)
    return TokenOut(access_token=token, user=user_out(user))


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id)
    _set_auth_cookie(response, token)
    return TokenOut(access_token=token, user=user_out(user))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserSettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name is not None:
        user.name = payload.name
    if payload.github_token is not None:
        user.github_token = payload.github_token.strip() or None
    if payload.llm_provider is not None:
        user.llm_provider = payload.llm_provider
    db.commit()
    db.refresh(user)
    return user_out(user)
