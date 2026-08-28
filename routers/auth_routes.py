"""Registration, login and current-user endpoints."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from auth import check_admin_role, create_access_token, get_current_user, hash_password, verify_password
from models import User
from schemas import TokenResponse, UserLogin, UserRegistration, UserResponse, UserUpdate

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/auth/register", response_model=UserResponse, status_code=201)
@router.post("/users/register", response_model=UserResponse, status_code=201)
def register(payload: UserRegistration, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(id=uuid4(), email=email, password_hash=hash_password(payload.password), full_name=payload.full_name)
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.post("/auth/login", response_model=TokenResponse)
@router.post("/users/login", response_model=TokenResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    """Accept Frontend JSON and OAuth2 password-form login payloads."""
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith("multipart/form-data"):
        form = await request.form()
        email, password = str(form.get("username", "")), str(form.get("password", ""))
    else:
        try:
            body = await request.json()
            email, password = str(body.get("email", body.get("username", ""))), str(body.get("password", ""))
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid JSON login payload") from None
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not password or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token({"sub": str(user.id)}))

@router.get("/auth/me", response_model=UserResponse)
def me(current: User = Depends(get_current_user)):
    return current

@router.put("/users/me", response_model=UserResponse)
@router.put("/auth/me", response_model=UserResponse)
def update_me(payload: UserUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.full_name is not None: current.full_name = payload.full_name.strip() or None
    if payload.password is not None: current.password_hash = hash_password(payload.password)
    current.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(current)
    return current

@router.delete("/users/{user_id}", response_model=UserResponse)
def deactivate_user(user_id: UUID, current: User = Depends(check_admin_role), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    user.is_active = False; user.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(user)
    return user
