import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.domain.repositories.user_repository import UserRepositoryInterface
from src.adapters.db.models import User, Role, Permission

class SQLAlchemyUserRepository(UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = (
            select(User)
            .where(User.id == uid, User.deleted_at.is_(None))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.email == email, User.deleted_at.is_(None))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        stmt = (
            select(User)
            .where(User.phone == phone, User.deleted_at.is_(None))
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_permission_by_name(self, name: str) -> Optional[Permission]:
        stmt = select(Permission).where(Permission.name == name, Permission.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(self, name: str) -> Role:
        role = Role(name=name)
        self.db.add(role)
        await self.db.flush()
        return role

    async def create_permission(self, name: str) -> Permission:
        permission = Permission(name=name)
        self.db.add(permission)
        await self.db.flush()
        return permission
