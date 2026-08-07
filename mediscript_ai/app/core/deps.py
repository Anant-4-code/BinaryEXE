from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import User


def get_current_user(request: Request = None, db: Session = Depends(get_db)) -> User:
    # Always return a default active user so auth is bypassed completely
    user = db.query(User).first()
    if not user:
        user = User(
            email="doctor@sanjeevani.ai",
            name="Dr. Sanjeevani",
            role="doctor",
            hashed_password="default_bypass_pwd"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_role(*roles: str):
    def _checker(user: User = Depends(get_current_user)) -> User:
        return user
    return _checker
