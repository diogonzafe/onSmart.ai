from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema, UserUpdate
from app.core.security import get_current_active_user

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/me", response_model=UserSchema)
async def get_current_user(
    current_user: User = Depends(get_current_active_user)
):
    return current_user

@router.put("/me", response_model=UserSchema)
async def update_current_user(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Update only provided fields
    if update_data.name is not None:
        current_user.name = update_data.name
    if update_data.picture is not None:
        current_user.picture = update_data.picture
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.delete("/me")
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Soft delete - just deactivate
    current_user.is_active = False
    db.commit()
    
    return {"message": "Account deactivated successfully"}