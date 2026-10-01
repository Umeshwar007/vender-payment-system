import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


database_url = os.environ.get("PAYMENT_DATABASE_URL")
if not database_url:
    raise RuntimeError("PAYMENT_DATABASE_URL is not set")

engine = create_async_engine(database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)