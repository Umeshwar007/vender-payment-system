import asyncio
import json
import logging
import os
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.invoice_service.app.db import SessionFactory, engine
from services.invoice_service.app.models import Invoice, ProcessedPaymentEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM_NAME = "payment-events"
GROUP_NAME = "invoice-payment-service"
CONSUMER_NAME = "invoice-payment-consumer"


async def ensure_consumer_group(client: Redis) -> None:
    try:
        await client.xgroup_create(
            STREAM_NAME,
            GROUP_NAME,
            id="0-0",
            mkstream=True,
        )
        logger.info("Created Redis consumer group %s", GROUP_NAME)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def process_event(fields: dict[str, str]) -> None:
    if fields.get("event_type") != "payment.succeeded":
        raise ValueError(f"Unexpected payment event: {fields.get('event_type')}")

    event_id = UUID(fields["event_id"])
    payload = json.loads(fields["payload"])

    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported payment event schema version")

    invoice_id = UUID(payload["invoice_id"])
    amount_cents = int(payload["amount_cents"])

    if amount_cents <= 0:
        raise ValueError("Payment amount must be greater than zero")

    async with SessionFactory.begin() as session:
        inserted = await session.execute(
            pg_insert(ProcessedPaymentEvent)
            .values(event_id=event_id)
            .on_conflict_do_nothing(
                index_elements=[ProcessedPaymentEvent.event_id]
            )
            .returning(ProcessedPaymentEvent.event_id)
        )

        if inserted.scalar_one_or_none() is None:
            logger.info("Skipping duplicate payment event %s", event_id)
            return

        invoice = await session.scalar(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .with_for_update()
        )

        if invoice is None:
            raise RuntimeError(f"Invoice {invoice_id} does not exist")

        new_amount_paid = invoice.amount_paid_cents + amount_cents
        if new_amount_paid > invoice.total_cents:
            raise RuntimeError(f"Payment would overpay invoice {invoice_id}")

        invoice.amount_paid_cents = new_amount_paid
        invoice.status = (
            "paid" if new_amount_paid == invoice.total_cents else "partially_paid"
        )

    logger.info("Updated invoice %s from payment event %s", invoice_id, event_id)


def flatten_messages(messages: list) -> list:
    return [
        (message_id, fields)
        for _, entries in messages
        for message_id, fields in entries
    ]


async def main() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await ensure_consumer_group(redis)
    logger.info("Listening to Redis stream %s", STREAM_NAME)

    try:
        while True:
            # Resume messages this consumer left pending before reading new ones.
            messages = await redis.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: "0-0"},
                count=10,
            )
            entries = flatten_messages(messages)

            if not entries:
                messages = await redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_NAME: ">"},
                    count=10,
                    block=5000,
                )
                entries = flatten_messages(messages)

            for message_id, fields in entries:
                try:
                    await process_event(fields)
                    await redis.xack(STREAM_NAME, GROUP_NAME, message_id)
                except Exception:
                    logger.exception(
                        "Could not process payment event %s",
                        message_id,
                    )
                    await asyncio.sleep(2)
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())