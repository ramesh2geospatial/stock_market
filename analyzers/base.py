"""
Abstract Base Class for sentiment analyzers.
"""
from abc import ABC, abstractmethod
from models.analysis import SentimentResult


class BaseSentimentAnalyzer(ABC):
    """Interface for all sentiment analysis engines."""

    @abstractmethod
    def analyze_text(self, text: str) -> SentimentResult:
        """Analyze raw text and return sentiment + basic highlights."""
        pass

    @abstractmethod
    def analyze_concall(self, text: str, quarter: str) -> SentimentResult:
        """
        Deep analysis of a concall transcript.
        Should extract: sentiment, highlights, concerns, milestones, future targets.
        """
        pass
