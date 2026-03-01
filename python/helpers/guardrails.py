import logging
import re

logger = logging.getLogger("guardrails")


async def log_guardrail_block(tool: str, reason: str, value, threshold) -> None:
    logger.warning(
        "Guardrail block: tool=%s reason=%s value=%s threshold=%s",
        tool, reason, value, threshold,
    )


# Prompt injection detection patterns
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+DAN", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(your\s+)?instructions", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
]


def check_prompt_injection(text: str) -> str | None:
    """Check text for common prompt injection patterns.
    Returns the matched pattern description if found, None otherwise."""
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            logger.warning(
                "Prompt injection detected: pattern=%s text_snippet=%s",
                pattern.pattern, match.group()[:100],
            )
            return match.group()
    return None
