"""
Tests for HTML transcript extraction in ScreenerProvider.
"""
import pytest
from unittest.mock import patch, MagicMock

from providers.screener_provider import ScreenerProvider


@pytest.fixture
def provider():
    return ScreenerProvider()


class TestHTMLTranscriptExtraction:
    def test_extract_html_transcript_basic(self, provider):
        """Extracts text from a basic HTML page."""
        html = """
        <html>
        <head><title>Concall Transcript</title></head>
        <body>
            <nav>Navigation menu items</nav>
            <article>
                <p>The management discussed revenue growth of 18% YoY to Rs 2,400 Cr.</p>
                <p>EBITDA margins expanded to 22% driven by operating leverage.</p>
                <p>We expect continued growth in the coming quarters with strong order pipeline.</p>
                <p>The capex program of Rs 500 Cr is on track for completion by Q4 FY26.</p>
                <p>Net debt reduced from Rs 1,800 Cr to Rs 1,500 Cr during the quarter.</p>
            </article>
            <footer>Footer content</footer>
        </body>
        </html>
        """
        result = provider._extract_html_transcript(html, "https://example.com/transcript")
        assert "revenue growth" in result.lower()
        assert "EBITDA" in result
        assert "Navigation menu" not in result
        assert "Footer content" not in result

    def test_extract_html_strips_scripts_and_styles(self, provider):
        """Removes script and style tags."""
        html = """
        <html><body>
            <script>var tracking = true;</script>
            <style>.header { color: red; }</style>
            <p>Revenue of Rs 2,400 Cr was strong this quarter with growth exceeding expectations.</p>
            <p>Management remains confident about the outlook for FY26 with expansion plans.</p>
            <p>The new manufacturing facility is expected to be operational by Q2 FY26.</p>
        </body></html>
        """
        result = provider._extract_html_transcript(html, "https://example.com/transcript")
        assert "tracking" not in result
        assert "color: red" not in result
        assert "Revenue of Rs 2,400 Cr" in result

    def test_extract_html_too_short(self, provider):
        """Returns empty string if extracted text is too short."""
        html = "<html><body><p>Short.</p></body></html>"
        result = provider._extract_html_transcript(html, "https://example.com")
        assert result == ""

    def test_extract_html_fallback_to_get_text(self, provider):
        """Falls back to get_text if structured extraction yields few elements."""
        html = """
        <html><body>
        Revenue of Rs 2,400 Cr was strong this quarter with growth exceeding expectations.
        Management remains confident about the outlook for FY26 with expansion plans.
        The new manufacturing facility is expected to be operational by Q2 FY26.
        EBITDA margins expanded to 22% driven by operating leverage and cost optimization.
        Net debt reduced significantly from Rs 1,800 Cr to Rs 1,500 Cr during the quarter.
        </body></html>
        """
        result = provider._extract_html_transcript(html, "https://example.com/transcript")
        # Should still extract text even without <p> tags
        assert len(result) > 100

    @patch("providers.screener_provider.requests.get")
    def test_download_routes_html_correctly(self, mock_get, provider):
        """download_transcript_text routes HTML content to _extract_html_transcript."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = """
        <html><body>
            <p>Revenue of Rs 2,400 Cr was strong this quarter with growth exceeding expectations.</p>
            <p>EBITDA margins expanded to 22% driven by operating leverage and cost optimization.</p>
            <p>Management discussed capex plans of Rs 500 Cr for the new manufacturing facility.</p>
            <p>Net debt reduced from Rs 1,800 Cr to Rs 1,500 Cr showing improved balance sheet.</p>
            <p>Order book stands at Rs 8,500 Cr providing strong revenue visibility for FY26.</p>
        </body></html>
        """
        mock_get.return_value = mock_response

        result = provider.download_transcript_text("https://example.com/transcript.html")
        assert len(result) > 100
        assert "revenue" in result.lower()

    @patch("providers.screener_provider.requests.get")
    def test_download_routes_pdf_correctly(self, mock_get, provider):
        """download_transcript_text routes PDF content to _extract_pdf_transcript."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"not a real pdf"
        mock_get.return_value = mock_response

        # Should try PDF extraction, fail, and return empty
        result = provider.download_transcript_text("https://example.com/transcript.pdf")
        assert result == ""  # Invalid PDF content
