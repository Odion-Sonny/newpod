from abc import ABC, abstractmethod
from typing import Optional, List
from src.adapters.db.models import User, Role, Permission

class UserRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_phone(self, phone: str) -> Optional[User]:
        pass

    @abstractmethod
    async def create(self, user: User) -> User:
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        pass

    @abstractmethod
    async def get_role_by_name(self, name: str) -> Optional[Role]:
        pass

    @abstractmethod
    async def get_permission_by_name(self, name: str) -> Optional[Permission]:
        pass

    @abstractmethod
    async def create_role(self, name: str) -> Role:
        pass

    @abstractmethod
    async def create_permission(self, name: str) -> Permission:
        pass
