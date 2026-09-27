import re


INJECTION_PATTERNS = [
    r"ignore\s+(all|any|your)\s+previous\s+instructions",
    r"ignore\s+previous\s+instructions",
    r"system\s+prompt",
    r"internal\s+refund\s+rules",
    r"approve\s+a\s+full\s+refund",
    r"you\s+are\s+a\s+system",
]


def detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()

    return any(
        re.search(pattern, lowered)
        for pattern in INJECTION_PATTERNS
    )
