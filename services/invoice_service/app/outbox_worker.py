import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select

from services.invoice_service.app.db import SessionFactory, engine
from services.invoice_service.app.models import OutboxEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM_NAME = "invoice-events"
BATCH_SIZE = 100


async def publish_pending_batch(redis: Redis) -> int:
    published_count = 0

    async with SessionFactory() as session:
        async with session.begin():
            result = await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            events = list(result)

            for event in events:
                try:
                    await redis.xadd(
                        STREAM_NAME,
                        {
                            "event_id": str(event.id),
                            "event_type": event.event_type,
                            "payload": json.dumps(event.payload),
                        },
                    )
                except Exception as exc:
                    event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                    logger.exception("Could not publish outbox event %s", event.id)
                    continue

                event.published_at = datetime.now(timezone.utc)
                event.last_error = None
                published_count += 1

    return published_count


async def run_worker() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)

    try:
        while True:
            try:
                published_count = await publish_pending_batch(redis)
            except Exception:
                logger.exception("Outbox poll failed")
                published_count = 0

            if published_count == 0:
                await asyncio.sleep(1)
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_worker())