import asyncio
from typing import AsyncGenerator, Generator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.database import Base, get_db
from src.main import app

from sqlalchemy.pool import NullPool

# Create a separate test database engine or use the dev database with rollback
# For simplicity, we run tests against the dev database but wrap every test in a transaction that rolls back.
test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Event loop fixture is managed automatically by pytest-asyncio

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    async def create_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(create_tables())
    yield

@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    # Start a transaction on the test session, rollback at the end
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = TestAsyncSessionLocal(bind=conn)
        
        yield session
        
        await session.close()
        await transaction.rollback()

@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # Override get_db to return our transactional session
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    
    # Use ASGITransport for testing FastAPI app directly without binding to port
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
        
    app.dependency_overrides.clear()
