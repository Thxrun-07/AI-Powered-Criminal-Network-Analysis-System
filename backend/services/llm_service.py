"""Hosted LLM Service module providing high-level interface for LLM operations."""
from backend.services.gemini_service import GeminiService, GeminiService as LLMService

__all__ = ["GeminiService", "LLMService"]
