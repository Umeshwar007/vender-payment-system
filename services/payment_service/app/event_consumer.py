import asyncio
import json
import logging
import os
from datetime import date
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import ResponseError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.payment_service.app.db import SessionFactory
from services.payment_service.app.models import InvoiceProjection, ProcessedEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STREAM_NAME = "invoice-events"
GROUP_NAME = "payment-service"
# Keep this name stable so this worker can resume its own pending messages
# after a restart.
CONSUMER_NAME = "payment-service-worker"


async def ensure_consumer_group(client: redis.Redis) -> None:
    try:
        await client.xgroup_create(
            name=STREAM_NAME,
            groupname=GROUP_NAME,
            id="0",
            mkstream=True,
        )
        logger.info("Created Redis consumer group %s", GROUP_NAME)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def process_event(fields: dict[str, str]) -> None:
    event_id = UUID(fields["event_id"])
    event_type = fields["event_type"]
    payload = json.loads(fields["payload"])

    if UUID(payload["event_id"]) != event_id:
        raise ValueError("Stream event ID does not match payload event ID")

    expected_status = {
        "invoice.approved": "approved",
        "invoice.scheduled": "scheduled",
    }.get(event_type)

    if expected_status is None:
        logger.warning("Ignoring unsupported invoice event type: %s", event_type)
        return

    if payload["status"] != expected_status:
        raise ValueError(f"Unexpected status for event type {event_type}")

    projection_values = {
        "invoice_id": UUID(payload["invoice_id"]),
        "vendor_id": UUID(payload["vendor_id"]),
        "invoice_number": payload["invoice_number"],
        "status": payload["status"],
        "due_date": date.fromisoformat(payload["due_date"]),
        "total_cents": int(payload["total_cents"]),
        "amount_paid_cents": int(payload["amount_paid_cents"]),
    }

    async with SessionFactory.begin() as session:
        # Insert the event ID first. If it already exists, this delivery was
        # processed previously, so don't apply its payload again.
        inserted_event = await session.execute(
            pg_insert(ProcessedEvent)
            .values(event_id=event_id)
            .on_conflict_do_nothing(index_elements=[ProcessedEvent.event_id])
            .returning(ProcessedEvent.event_id)
        )

        if inserted_event.scalar_one_or_none() is None:
            logger.info("Skipping duplicate event %s", event_id)
            return

        await session.execute(
            pg_insert(InvoiceProjection)
            .values(**projection_values)
            .on_conflict_do_update(
                index_elements=[InvoiceProjection.invoice_id],
                set_={
                    "vendor_id": projection_values["vendor_id"],
                    "invoice_number": projection_values["invoice_number"],
                    "status": projection_values["status"],
                    "due_date": projection_values["due_date"],
                    "total_cents": projection_values["total_cents"],
                    "amount_paid_cents": projection_values["amount_paid_cents"],
                },
            )
        )

    logger.info("Updated invoice projection for event %s", event_id)


async def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    client = redis.from_url(redis_url, decode_responses=True)

    await ensure_consumer_group(client)
    logger.info("Listening to Redis stream %s", STREAM_NAME)

    try:
        while True:
            logger.info("Checking for this worker's pending messages")
            messages = await client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: "0-0"},
                count=10,
            )
            logger.info(
                "Pending read returned %d stream result(s)",
                len(messages or []),
            )
            if not messages or not any(entries for _, entries in messages):
                logger.info("Waiting for new messages")
                messages = await client.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_NAME: ">"},
                    count=10,
                    block=5000,
                )

            for _, entries in messages or []:
                logger.info("Received %d message(s)", len(entries))
                for message_id, fields in entries:
                    try:
                        await process_event(fields)
                        await client.xack(
                            STREAM_NAME,
                            GROUP_NAME,
                            message_id,
                        )
                    except Exception:
                        logger.exception(
                            "Could not process Redis message %s",
                            message_id,
                        )
                        await asyncio.sleep(2)
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())