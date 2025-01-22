from collections.abc import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from security.database import get_db_connection

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