from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from app.db.database import get_db
from app.models.user import User, AuthProvider
from app.schemas.user import (
    LoginRequest, RegisterRequest, RefreshTokenRequest,
    Token, User as UserSchema, ChangePassword
)
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    verify_token, revoke_refresh_token,
    get_current_active_user
)
from app.core.oauth import google_oauth

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=UserSchema)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = User(
        id=str(uuid.uuid4()),
        email=request.email,
        name=request.name,
        hashed_password=get_password_hash(request.password),
        provider=AuthProvider.LOCAL,
        is_verified=True  # For simplicity, auto-verify. In production, send verification email
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is using OAuth
    if user.provider != AuthProvider.LOCAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please use {user.provider.value} to login"
        )
    
    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    # Verify refresh token
    payload = verify_token(request.refresh_token, token_type="refresh")
    email = payload.get("sub")
    
    # Get user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Revoke old refresh token
    revoke_refresh_token(request.refresh_token)
    
    # Create new tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/logout")
async def logout(
    refresh_token: RefreshTokenRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Revoke refresh token
    revoke_refresh_token(refresh_token.refresh_token)
    
    return {"message": "Successfully logged out"}

@router.get("/google")
async def google_login():
    """Initiate Google OAuth flow"""
    auth_url = google_oauth.get_auth_url()
    return RedirectResponse(url=auth_url)

@router.get("/google/callback")
async def google_callback(
    code: str,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for tokens
        token_data = await google_oauth.exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        
        # Get user info
        user_info = await google_oauth.get_user_info(access_token)
        
        # Check if user exists
        user = db.query(User).filter(User.email == user_info["email"]).first()
        
        if not user:
            # Create new user
            user = User(
                id=str(uuid.uuid4()),
                email=user_info["email"],
                name=user_info.get("name", ""),
                google_id=user_info["id"],
                picture=user_info.get("picture"),
                provider=AuthProvider.GOOGLE,
                is_verified=True,
                is_active=True
            )
            db.add(user)
        else:
            # Update existing user
            user.last_login = datetime.utcnow()
            if not user.google_id:
                user.google_id = user_info["id"]
            if not user.picture:
                user.picture = user_info.get("picture")
        
        db.commit()
        db.refresh(user)
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        # Redirect to frontend with tokens
        frontend_url = f"http://localhost:3000/auth-callback"
        return RedirectResponse(
            url=f"{frontend_url}?access_token={access_token}&refresh_token={refresh_token}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/change-password")
async def change_password(
    request: ChangePassword,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Check if user has a password (not OAuth)
    if current_user.provider != AuthProvider.LOCAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth users cannot change password"
        )
    
    # Verify old password
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}