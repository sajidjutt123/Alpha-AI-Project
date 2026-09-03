"""Background workers.

The Twilio webhook stores the message, enqueues a job, and returns 200
immediately. In the MVP the "queue" is FastAPI BackgroundTasks
(`InlineMessageProcessor`); the `MessageProcessor` interface is designed so
Redis/Arq or a dedicated worker can replace it without touching webhook
code (Phase 8+).
"""

from app.workers.messaging import InboundMessageJob, InlineMessageProcessor, MessageProcessor

__all__ = ["InboundMessageJob", "InlineMessageProcessor", "MessageProcessor"]
