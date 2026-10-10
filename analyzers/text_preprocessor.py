"""
Text preprocessor for concall transcripts.
Strips boilerplate (safe-harbor disclaimers, participant lists, operator scripts,
page headers/footers) so the Gemini prompt receives maximum signal per token.

Key design decisions:
- Preserves Q&A section (most valuable for analyst pushback and management commitments)
- If truncation is needed, cuts from opening remarks first, not the end
- Adds [Q&A SECTION] marker so Gemini can weight analyst dialogue appropriately
- Increased limit to 200K chars (Gemini 2.x supports 1M tokens)
"""
import re


# Patterns that match safe-harbor / disclaimer blocks
_DISCLAIMER_PATTERNS = [
    # Forward-looking statements disclaimer
    re.compile(
        r"(?:this|the)\s+(?:transcript|document|call|presentation)\s+"
        r"(?:contains|may contain|includes)\s+.*?forward[- ]looking\s+statements?"
        r".*?(?:\.\s*\n|\n\n)",
        re.IGNORECASE | re.DOTALL,
    ),
    # "E&OE" / errors-and-omissions disclaimer
    re.compile(
        r"(?:^|\n)\s*(?:e\s*&\s*o\s*e|errors?\s+and\s+omissions?\s+excepted).*?(?:\n\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Generic disclaimer blocks
    re.compile(
        r"(?:^|\n)\s*(?:disclaimer|legal\s+notice|safe\s+harbor)\s*[:\-]?\s*\n.*?(?:\n\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    # "This transcript has been edited for readability" boilerplate
    re.compile(
        r"(?:this\s+transcript\s+(?:has\s+been|was)\s+(?:edited|lightly\s+edited|prepared)"
        r".*?(?:\.\s*\n|\n\n))",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Patterns for participant/attendee list blocks
_PARTICIPANT_PATTERNS = [
    # "List of Participants" or "Management Participants" blocks
    re.compile(
        r"(?:^|\n)\s*(?:list\s+of\s+)?(?:management\s+|analyst\s+)?"
        r"(?:participants?|paneli?sts?|speakers?|attendees?)\s*[:\-]?\s*\n"
        r"(?:.*?\n){1,30}?\s*\n",
        re.IGNORECASE,
    ),
    # Numbered participant lists like "1. Mr. X - CFO\n2. Ms. Y - CEO"
    re.compile(
        r"(?:^|\n)(?:\s*\d+\.\s*(?:Mr\.|Ms\.|Mrs\.|Dr\.|Shri|Smt).*?\n){3,}",
        re.IGNORECASE,
    ),
]

# Operator housekeeping lines
_OPERATOR_PATTERNS = [
    re.compile(
        r"(?:^|\n)\s*(?:operator|moderator)\s*:\s*"
        r"(?:thank\s+you|ladies\s+and\s+gentlemen|good\s+(?:morning|afternoon|evening)"
        r"|welcome|we\s+will\s+now\s+begin|the\s+next\s+question|we\s+(?:have|take)\s+the\s+next)"
        r".*?(?:\.\s*\n|\n)",
        re.IGNORECASE,
    ),
    # "Please stand by" / "conference is being recorded"
    re.compile(
        r"(?:^|\n).*?(?:please\s+stand\s+by|conference\s+(?:is|will)\s+(?:now\s+)?be(?:ing)?\s+recorded"
        r"|press\s+\*\s*1|press\s+star\s+(?:one|1)|unmute\s+your\s+(?:line|phone)).*?\n",
        re.IGNORECASE,
    ),
]

# Page header/footer artifacts from PDF extraction
_PAGE_ARTIFACT_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:page\s+\d+\s+(?:of\s+\d+)?|confidential|for\s+private\s+circulation"
    r"|\d+\s*\|\s*page)\s*(?:\n|$)",
    re.IGNORECASE,
)

# Repeated company name lines (often PDF headers)
_REPEATED_HEADER_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[A-Z][A-Za-z&. ]{2,40}(?:Limited|Ltd\.?|Private|Corp\.?|Inc\.?))\s*\n"
    r"\s*(?:Q[1-4]\s+FY\s*\d{2,4}\s+)?(?:Earnings?\s+(?:Call|Conference)|Con\s*-?\s*Call"
    r"|Transcript)\s*\n",
    re.IGNORECASE,
)

# Q&A section detection patterns
_QA_START_PATTERNS = [
    re.compile(
        r"(?:^|\n)\s*(?:question[- ]?and[- ]?answer|q\s*&\s*a|q\s*and\s*a)\s*(?:session|segment|round)?\s*[:\-]?\s*\n",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*(?:we\s+(?:will|shall)\s+now\s+(?:begin|open|start)\s+(?:the\s+)?(?:q\s*&\s*a|question))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*(?:the\s+first\s+question\s+(?:is\s+from|comes\s+from))",
        re.IGNORECASE,
    ),
    # Additional patterns for common Indian concall formats
    re.compile(
        r"(?:^|\n)\s*(?:questions?\s+and\s+answers?)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*(?:analyst\s+questions?)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*(?:interactive\s+session|discussion\s+session)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    ),
    # Hindi-English hybrid patterns
    re.compile(
        r"(?:^|\n)\s*(?:sawal\s+jawab|prashn\s+uttar)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    ),
]

# ── Speaker Diarization ──────────────────────────────────────────────

# Title keywords for classifying speakers into roles
_MANAGEMENT_TITLES = re.compile(
    r"\b(?:MD|CEO|CFO|COO|CTO|CIO|CMO|Director|Chairman|Chairperson|President|Vice\s*President"
    r"|VP|Head|Chief|Managing|Executive|Promoter|Founder|Co-Founder|Whole\s*Time"
    r"|Joint\s+(?:MD|Managing)\b|Additional\s+Director|Company\s+Secretary)\b",
    re.IGNORECASE,
)

_ANALYST_TITLES = re.compile(
    r"\b(?:Analyst|Research|Securities|Fund|Capital|Brokerage|Advisors?"
    r"|AMC|Asset\s+Management|Portfolio|Investment|Wealth|Mutual\s+Fund"
    r"|Institutional|Equity|Markets?|Financial\s+Services)\b",
    re.IGNORECASE,
)

_MODERATOR_TITLES = re.compile(
    r"\b(?:Operator|Moderator|Host|Chorus\s+Call|Conference\s+Operator"
    r"|Coordinator|Emcee|Compere)\b",
    re.IGNORECASE,
)

# Patterns to detect speaker turns at line starts
# Matches: "Name - Title:", "Name (Title):", "Mr. Name:", "Name:"
_SPEAKER_LINE_PATTERNS = [
    # "Rajesh Kumar - Managing Director:" or "Rajesh Kumar, CEO:"
    re.compile(
        r"^\s*([A-Z][A-Za-z.\s]{2,40})\s*[-–,]\s*([A-Za-z.\s,&]{3,60})\s*:\s*$",
        re.MULTILINE,
    ),
    # "Mr. Rajesh Kumar (CEO):" or "Rajesh Kumar (MD & CEO):"
    re.compile(
        r"^\s*(?:(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+)?([A-Z][A-Za-z.\s]{2,40})\s*\(([^)]{2,60})\)\s*:\s*$",
        re.MULTILINE,
    ),
    # "Mr. Rajesh Kumar:" or "Rajesh Kumar:" (name only, no title)
    re.compile(
        r"^\s*(?:(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+)?([A-Z][A-Za-z.\s]{2,40})\s*:\s*$",
        re.MULTILINE,
    ),
    # "Management:" or "Analyst:" (generic role labels)
    re.compile(
        r"^\s*(Management|Analyst|Moderator|Operator|Speaker\s*\d*)\s*:\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]


def _find_qa_start(text: str) -> int:
    """Find the character position where the Q&A section begins.
    Returns -1 if no Q&A section is detected.
    Issue #27: Returns the EARLIEST match across all patterns, not the first pattern's match."""
    earliest = -1
    for pattern in _QA_START_PATTERNS:
        match = pattern.search(text)
        if match:
            pos = match.start()
            if earliest == -1 or pos < earliest:
                earliest = pos
    return earliest


def preprocess_transcript(text: str, max_chars: int = 200000) -> str:
    """
    Clean a raw concall transcript to maximise signal for LLM analysis.

    Removes:
      - Safe-harbor / forward-looking-statements disclaimers
      - Participant / attendee list blocks
      - Operator housekeeping lines (mute/unmute, stand-by, recording notice)
      - PDF page headers/footers
      - Excessive whitespace & blank lines

    Preserves (in priority order):
      1. Q&A section (analyst questions + management answers) — HIGHEST priority
      2. Management opening remarks & financial commentary
      3. All financial data, guidance, and numbers

    Returns cleaned text truncated to *max_chars*.
    """
    if not text or not text.strip():
        return ""

    cleaned = text

    # 1. Strip disclaimers
    for pat in _DISCLAIMER_PATTERNS:
        cleaned = pat.sub("\n", cleaned)

    # 2. Strip participant blocks
    for pat in _PARTICIPANT_PATTERNS:
        cleaned = pat.sub("\n", cleaned)

    # Issue #28: Detect Q&A position BEFORE operator stripping
    # (operator patterns can remove the Q&A announcement line)
    qa_pos = _find_qa_start(cleaned)

    # 3. Strip operator housekeeping (after Q&A detection)
    for pat in _OPERATOR_PATTERNS:
        cleaned = pat.sub("\n", cleaned)

    # 4. Strip page artifacts
    cleaned = _PAGE_ARTIFACT_PATTERN.sub("\n", cleaned)

    # 5. Strip repeated PDF headers
    cleaned = _REPEATED_HEADER_PATTERN.sub("\n", cleaned)

    # 6. Collapse runs of 3+ blank lines into 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 7. Collapse runs of spaces (but keep newlines)
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)

    # 8. Strip leading/trailing whitespace per line
    lines = [line.strip() for line in cleaned.split("\n")]
    cleaned = "\n".join(lines)

    # 9. Insert [Q&A SECTION] marker for Gemini
    # Since text was modified by operator stripping, re-detect if original pos was found
    if qa_pos > 0:
        # Try to find a re-anchor near the original proportional position
        new_qa_pos = _find_qa_start(cleaned)
        if new_qa_pos > 0:
            cleaned = cleaned[:new_qa_pos] + "\n\n[Q&A SECTION BEGINS]\n\n" + cleaned[new_qa_pos:]
        else:
            # Original Q&A marker was removed by operator stripping;
            # insert at proportional position
            proportional_pos = int(len(cleaned) * (qa_pos / max(len(text), 1)))
            if proportional_pos > 100 and proportional_pos < len(cleaned):
                # Find nearest paragraph break
                para_break = cleaned.rfind("\n\n", 0, proportional_pos + 500)
                if para_break > proportional_pos - 500:
                    cleaned = cleaned[:para_break] + "\n\n[Q&A SECTION BEGINS]\n" + cleaned[para_break:]
    else:
        # Try detection on cleaned text as well
        new_qa_pos = _find_qa_start(cleaned)
        if new_qa_pos > 0:
            cleaned = cleaned[:new_qa_pos] + "\n\n[Q&A SECTION BEGINS]\n\n" + cleaned[new_qa_pos:]

    # 10. Speaker diarization — inject role markers
    cleaned = diarize_transcript(cleaned)

    # 11. Final trim
    cleaned = cleaned.strip()

    # 12. Smart truncation — prioritize Q&A section
    if len(cleaned) > max_chars:
        qa_marker_pos = cleaned.find("[Q&A SECTION BEGINS]")

        if qa_marker_pos > 0:
            # Preserve Q&A section by cutting from opening remarks
            qa_section = cleaned[qa_marker_pos:]
            opening_section = cleaned[:qa_marker_pos]

            if len(qa_section) <= max_chars * 0.8:
                # Q&A fits — allocate remaining budget to opening remarks
                opening_budget = max_chars - len(qa_section) - 100  # 100 chars buffer
                if opening_budget > 0:
                    truncated_opening = opening_section[:opening_budget]
                    last_period = truncated_opening.rfind(".")
                    if last_period > opening_budget * 0.7:
                        truncated_opening = truncated_opening[:last_period + 1]
                    cleaned = truncated_opening + "\n\n[...OPENING REMARKS TRUNCATED...]\n\n" + qa_section
                else:
                    cleaned = qa_section[:max_chars]
            else:
                # Q&A itself is very long — take last 80% of budget for Q&A
                qa_budget = int(max_chars * 0.8)
                opening_budget = max_chars - qa_budget - 100
                truncated_opening = opening_section[:max(opening_budget, 0)]
                truncated_qa = qa_section[:qa_budget]
                cleaned = truncated_opening + "\n\n[...TRUNCATED...]\n\n" + truncated_qa
        else:
            # No Q&A detected — truncate from end at paragraph/sentence boundary
            # Issue #29: Avoid cutting on abbreviations like "Rs." by looking
            # for paragraph breaks first, then sentence ends
            cleaned = cleaned[:max_chars]
            # Prefer paragraph break
            para_break = cleaned.rfind("\n\n")
            if para_break > max_chars * 0.8:
                cleaned = cleaned[:para_break]
            else:
                # Fall back to sentence boundary (look for period + space/newline)
                last_period = cleaned.rfind(". ")
                if last_period > max_chars * 0.8:
                    cleaned = cleaned[:last_period + 1]
                else:
                    last_newline_period = cleaned.rfind(".\n")
                    if last_newline_period > max_chars * 0.8:
                        cleaned = cleaned[:last_newline_period + 1]

    return cleaned


# ── Speaker Diarization Functions ────────────────────────────────────

def detect_speakers(text: str) -> list[dict]:
    """
    Detect speakers in a transcript and classify them by role.

    Returns a list of speaker dicts:
        {"name": str, "title": str, "role": str, "positions": [int, ...]}

    Roles: "management", "analyst", "moderator", "unknown"
    """
    speakers = {}  # name -> {"name", "title", "role", "positions"}

    for pattern in _SPEAKER_LINE_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            name = groups[0].strip().rstrip(".")
            title = groups[1].strip() if len(groups) > 1 and groups[1] else ""
            position = match.start()

            # Normalize name (remove honorifics for dedup)
            clean_name = re.sub(r"^(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+", "", name, flags=re.IGNORECASE).strip()
            if not clean_name or len(clean_name) < 2:
                continue

            # Classify role
            role = _classify_speaker_role(clean_name, title)

            key = clean_name.lower()
            if key in speakers:
                speakers[key]["positions"].append(position)
                # Update title if we got a better one
                if title and not speakers[key]["title"]:
                    speakers[key]["title"] = title
                    speakers[key]["role"] = _classify_speaker_role(clean_name, title)
            else:
                speakers[key] = {
                    "name": clean_name,
                    "title": title,
                    "role": role,
                    "positions": [position],
                }

    return list(speakers.values())


def _classify_speaker_role(name: str, title: str) -> str:
    """Classify a speaker as management, analyst, moderator, or unknown."""
    combined = f"{name} {title}"

    # Check for generic labels first
    name_lower = name.lower().strip()
    if name_lower in ("operator", "moderator", "host"):
        return "moderator"
    if name_lower in ("management",):
        return "management"
    if name_lower in ("analyst",):
        return "analyst"

    # Check title keywords
    if _MODERATOR_TITLES.search(combined):
        return "moderator"
    if _MANAGEMENT_TITLES.search(combined):
        return "management"
    if _ANALYST_TITLES.search(combined):
        return "analyst"

    return "unknown"


def diarize_transcript(text: str) -> str:
    """
    Inject speaker role markers into the transcript text.

    If ≥3 speakers are detected, inserts markers like:
        [MANAGEMENT - Rajesh Kumar, CEO]
        [ANALYST - Sanjay Mehta, HDFC Securities]
        [MODERATOR]

    If <3 speakers are detected, returns the text unchanged (graceful fallback).
    Markers are additive — original text content is fully preserved.
    """
    speakers = detect_speakers(text)

    if len(speakers) < 3:
        return text  # Graceful fallback

    # Build replacement map: position -> marker string
    insertions = []  # list of (position, end_of_speaker_line, marker_text)

    for speaker in speakers:
        role = speaker["role"].upper()
        name = speaker["name"]
        title = speaker["title"]

        if role == "MODERATOR":
            marker = "[MODERATOR]"
        elif role == "UNKNOWN":
            marker = f"[SPEAKER - {name}]"
        else:
            if title:
                marker = f"[{role} - {name}, {title}]"
            else:
                marker = f"[{role} - {name}]"

        for pos in speaker["positions"]:
            insertions.append((pos, marker))

    if not insertions:
        return text

    # Sort by position (reverse) so we can insert without shifting offsets
    insertions.sort(key=lambda x: x[0], reverse=True)

    result = text
    for pos, marker in insertions:
        # Find the start of the speaker line
        line_start = result.rfind("\n", 0, pos)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # skip the newline itself

        # Insert marker before the speaker line
        result = result[:line_start] + marker + "\n" + result[line_start:]

    return result

