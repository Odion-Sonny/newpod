from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import decode_token
from src.adapters.db.models import User
from src.adapters.db.repositories.user_repository import SQLAlchemyUserRepository

security_scheme = HTTPBearer()

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token.credentials)
    if not payload or payload.get("type") != "access":
        raise credentials_exception
        
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
        
    user_repo = SQLAlchemyUserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise credentials_exception
        
    return user

# Helper dependency for role verification (RBAC)
def check_role(required_role: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = [role.name for role in current_user.roles]
        if required_role not in user_roles and "ADMIN" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to perform this action"
            )
        return current_user
    return role_checker

from typing import Optional

security_scheme_optional = HTTPBearer(auto_error=False)

async def get_current_user_optional(
    token: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_token(token.credentials)
        if not payload or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_repo = SQLAlchemyUserRepository(db)
        return await user_repo.get_by_id(user_id)
    except Exception:
        return None
