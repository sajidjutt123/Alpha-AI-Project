"""Background workers (Phase 4/8: async AI processing).

The Twilio webhook stores the message, enqueues a job, and returns 200
immediately. In the MVP the "queue" is an in-process task runner (FastAPI
BackgroundTasks); the interface is designed so Redis/Arq or a proper queue
can replace it without touching the webhook code.
"""
