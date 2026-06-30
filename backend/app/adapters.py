"""Backend adapter layer for CLI package (scopepilot).

Architecture boundary:
  src/scopepilot/  ← CLI package (sync, typer + rich)
  backend/app/     ← Web backend (async, FastAPI)
       └── services/ ← SHOULD be the sole consumer of scopepilot internals
       └── api/v1/   ← MUST NOT import scopepilot directly

Current state (P1): backend/services/*.py imports from scopepilot directly.
This is acceptable short-term because both run in the same process. For Phase 2+
this should be extracted into a shared core/ package.

Rule:
  - api/v1/ routes → import from services/ or adapters/ only
  - services/ → may import scopepilot internals
  - New code → go through adapter functions below
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_llm_provider():
    """Create an LLM provider from environment config.

    Wraps scopepilot.ai.create_provider with backend-appropriate logging.
    """
    from scopepilot.ai import create_provider, AIError
    try:
        provider = create_provider()
        logger.info("LLM provider created successfully")
        return provider
    except AIError as e:
        logger.error("Failed to create LLM provider: %s", e)
        raise


def create_analysis_pipeline(provider=None):
    """Create an AnalysisPipeline with the configured LLM provider."""
    from scopepilot.analyzer import AnalysisPipeline
    if provider is None:
        provider = create_llm_provider()
    return AnalysisPipeline(provider=provider)


def batch_analyze_tickets(tickets: list[dict]) -> list:
    """Analyze tickets in batch via the CLI pipeline.

    Args:
        tickets: List of ticket dicts with 'key', 'summary', 'description', etc.

    Returns:
        List of AnalysisResult objects.
    """
    pipeline = create_analysis_pipeline()
    return pipeline.analyze_tickets_batch(tickets)


def analyze_sprint_summary(sprint_name: str, ticket_analyses: list) -> object:
    """Generate a sprint-level analysis summary."""
    pipeline = create_analysis_pipeline()
    return pipeline.analyze_sprint(sprint_name, ticket_analyses)


def generate_sprint_report(sprint: dict, tickets: list[dict]) -> str:
    """Generate a sprint report markdown.

    Wraps scopepilot.report.generate_sprint_report.
    """
    from scopepilot.report import generate_sprint_report as _gen
    return _gen(sprint, tickets)
