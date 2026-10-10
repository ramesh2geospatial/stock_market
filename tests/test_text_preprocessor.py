"""
Tests for text_preprocessor — speaker diarization, Q&A detection, and boilerplate removal.
"""
import pytest

from analyzers.text_preprocessor import (
    detect_speakers,
    diarize_transcript,
    _classify_speaker_role,
    _find_qa_start,
    preprocess_transcript,
)


class TestSpeakerDetection:
    def test_detect_management_with_title_dash(self):
        """Detects 'Name - Title:' pattern."""
        text = """
Rajesh Kumar - Managing Director:
We had a strong quarter with 18% revenue growth.

Suresh Gupta - CFO:
Our EBITDA margin expanded to 22%.

Sanjay Mehta - HDFC Securities:
What about competitive pressures?

Operator:
Thank you for standing by.
"""
        speakers = detect_speakers(text)
        assert len(speakers) >= 3
        names = {s["name"].lower() for s in speakers}
        assert "rajesh kumar" in names
        assert "suresh gupta" in names

    def test_detect_management_with_parenthetical_title(self):
        """Detects 'Name (Title):' pattern."""
        text = """
Rajesh Kumar (CEO):
Revenue grew 18% YoY.

Suresh Gupta (CFO):
Margins improved.

Sanjay Mehta (Analyst):
Questions about margins.

Moderator:
Next question please.
"""
        speakers = detect_speakers(text)
        assert len(speakers) >= 3

    def test_detect_honorific_prefixed_names(self):
        """Detects 'Mr./Dr./Shri Name:' patterns."""
        text = """
Mr. Rajesh Kumar:
Our performance was strong.

Dr. Priya Sharma:
We see positive trends.

Shri Mohan Lal:
The business is growing.
"""
        speakers = detect_speakers(text)
        assert len(speakers) >= 3
        # Names should be cleaned (honorifics removed for dedup)
        names = {s["name"] for s in speakers}
        assert any("Rajesh" in n for n in names)

    def test_graceful_fallback_with_few_speakers(self):
        """Returns unchanged text when <3 speakers found."""
        text = "This transcript has no speaker labels at all. Just plain text."
        result = diarize_transcript(text)
        assert result == text  # No changes

    def test_graceful_fallback_with_two_speakers(self):
        """Returns unchanged text when only 2 speakers found."""
        text = """
Rajesh Kumar - CEO:
Revenue grew 18%.

Suresh Gupta - CFO:
Margins improved.
"""
        result = diarize_transcript(text)
        assert result == text  # Only 2 speakers, no markers

    def test_markers_injected_with_enough_speakers(self):
        """Injects role markers when ≥3 speakers detected."""
        text = """Rajesh Kumar - Managing Director:
Revenue grew 18%.

Suresh Gupta - CFO:
Margins improved.

Sanjay Mehta - HDFC Securities:
What about competitive pressures?

Operator:
Next question please.
"""
        result = diarize_transcript(text)
        assert "[MANAGEMENT" in result
        assert "[ANALYST" in result or "[SPEAKER" in result

    def test_markers_preserve_original_content(self):
        """Original text content is preserved — markers are additive only."""
        text = """Rajesh Kumar - Managing Director:
Revenue grew 18%.

Suresh Gupta - CFO:
Margins improved.

Sanjay Mehta - HDFC Securities:
What about competitive pressures?

Operator:
Next question.
"""
        result = diarize_transcript(text)
        assert "Revenue grew 18%." in result
        assert "Margins improved." in result
        assert "What about competitive pressures?" in result


class TestSpeakerClassification:
    def test_classify_ceo(self):
        assert _classify_speaker_role("Rajesh Kumar", "CEO") == "management"

    def test_classify_cfo(self):
        assert _classify_speaker_role("Suresh Gupta", "CFO") == "management"

    def test_classify_managing_director(self):
        assert _classify_speaker_role("Rajesh", "Managing Director") == "management"

    def test_classify_analyst_by_firm(self):
        assert _classify_speaker_role("Sanjay Mehta", "HDFC Securities") == "analyst"

    def test_classify_analyst_by_role(self):
        assert _classify_speaker_role("Sanjay", "Research Analyst") == "analyst"

    def test_classify_moderator(self):
        assert _classify_speaker_role("Operator", "") == "moderator"

    def test_classify_unknown(self):
        assert _classify_speaker_role("Random Person", "Some Title") == "unknown"


class TestQADetection:
    def test_standard_qa_pattern(self):
        text = "Opening remarks.\n\nQuestion and Answer Session:\n\nFirst question..."
        pos = _find_qa_start(text)
        assert pos > 0

    def test_qanda_pattern(self):
        text = "Opening remarks.\n\nQ&A:\n\nFirst question..."
        pos = _find_qa_start(text)
        assert pos > 0

    def test_questions_and_answers_pattern(self):
        """New pattern: 'Questions and Answers'."""
        text = "Opening remarks.\n\nQuestions and Answers:\n\nFirst question..."
        pos = _find_qa_start(text)
        assert pos > 0

    def test_analyst_questions_pattern(self):
        """New pattern: 'Analyst Questions'."""
        text = "Opening remarks.\n\nAnalyst Questions:\n\nFirst question..."
        pos = _find_qa_start(text)
        assert pos > 0

    def test_no_qa_returns_negative(self):
        text = "Just a plain transcript with no Q&A section markers."
        pos = _find_qa_start(text)
        assert pos == -1


class TestPreprocessIntegration:
    def test_preprocess_inserts_qa_marker(self):
        text = """
Safe harbor statement. Forward-looking statements may not reflect actual results.

Management Commentary:
Revenue grew 18% YoY to Rs 2,400 Cr.

Question and Answer Session:
Analyst: What about margins?
CEO: We expect margins to improve.
"""
        result = preprocess_transcript(text, max_chars=10000)
        assert "[Q&A SECTION BEGINS]" in result

    def test_preprocess_strips_disclaimers(self):
        text = """
This document contains forward-looking statements that involve risks.

Revenue grew 18% YoY.
"""
        result = preprocess_transcript(text, max_chars=10000)
        assert "forward-looking statements" not in result.lower()
        assert "Revenue grew 18%" in result

    def test_preprocess_handles_empty_text(self):
        result = preprocess_transcript("", max_chars=10000)
        assert result == ""

    def test_preprocess_handles_none_text(self):
        result = preprocess_transcript(None, max_chars=10000)
        assert result == ""
