from collections.abc import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

def get_db_connection(use_async=True):
    TEMP_DB_LOC = "dev.sqlight"
    ASYNC_TEMP_DATABASE_URL = f"sqlite+aiosqlite:///./{TEMP_DB_LOC}"
    TEMP_DATABASE_URL = f"sqlite:///./{TEMP_DB_LOC}"
    url = ASYNC_TEMP_DATABASE_URL if use_async else TEMP_DATABASE_URL
    return url

class DBSession:

    # Must put connection info as a class variable so that pytests run.
    connection_info = get_db_connection()

    @staticmethod
    async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine(DBSession.connection_info, echo=False)
        # factory = async_sessionmaker(engine)
        factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except exc.SQLAlchemyError as error:
                await session.rollback()
                raise error