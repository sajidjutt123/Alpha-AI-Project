"""AI agent orchestration (Phase 5/6: LangGraph workflow).

Pipeline: intent detection -> information extraction -> qualification ->
property search -> business rules -> response generation -> validation.
The LLM never writes to the database directly; it calls validated tools.
"""
