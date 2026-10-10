"""
Unit tests for MultiSourceDocFetcher (providers/multi_source_doc_fetcher.py).
"""
import os
import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.stock import UnifiedDocument, DocumentLink
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher, normalize_quarter_label
from storage.sqlite_store import SQLiteStore


def test_normalize_quarter_label():
    assert normalize_quarter_label("Jul 2025") == "Q1 FY26"
    assert normalize_quarter_label("May 2026") == "Q4 FY26"
    assert normalize_quarter_label("Q1 FY26") == "Q1 FY26"
    assert normalize_quarter_label("Q4 FY2026") == "Q4 FY26"
    assert normalize_quarter_label("Oct 2025") == "Q2 FY26"
    assert normalize_quarter_label("Jan 2026") == "Q3 FY26"


def test_3_tier_fallback_tier1_success(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    bse_doc1 = UnifiedDocument(
        symbol="HDFCBANK",
        quarter="Q1 FY26",
        title="Transcript Q1 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/t1.pdf",
        source_used="BSE",
        category="transcript",
    )
    bse_doc2 = UnifiedDocument(
        symbol="HDFCBANK",
        quarter="Q1 FY26",
        title="Presentation Q1 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/p1.pdf",
        source_used="BSE",
        category="presentation",
    )
    bse_doc3 = UnifiedDocument(
        symbol="HDFCBANK",
        quarter="Q1 FY26",
        title="Financial Results Q1 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/r1.pdf",
        source_used="BSE",
        category="financial_results",
    )

    fetcher.bse.fetch_documents = MagicMock(return_value=[bse_doc1, bse_doc2, bse_doc3])
    fetcher.screener.fetch_documents = MagicMock(return_value=[])
    fetcher.nse.fetch_documents = MagicMock(return_value=[])

    docs = fetcher.fetch_documents("HDFCBANK", force_refresh=True)

    assert len(docs) == 3
    assert all(d.source_used == "BSE" for d in docs)
    fetcher.bse.fetch_documents.assert_called_once()
    fetcher.screener.fetch_documents.assert_not_called()
    fetcher.nse.fetch_documents.assert_not_called()


def test_3_tier_fallback_tier2_called_when_tier1_empty(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    screener_link1 = DocumentLink(
        title="Concall Transcript Jul 2025",
        url="https://www.screener.in/transcripts/t2.pdf",
        category="transcript",
        date_hint="Jul 2025",
    )
    screener_link2 = DocumentLink(
        title="Investor Presentation Jul 2025",
        url="https://www.screener.in/presentations/p2.pdf",
        category="presentation",
        date_hint="Jul 2025",
    )
    screener_link3 = DocumentLink(
        title="Financial Results Jul 2025",
        url="https://www.screener.in/results/r2.pdf",
        category="financial_results",
        date_hint="Jul 2025",
    )

    fetcher.bse.fetch_documents = MagicMock(return_value=[])
    fetcher.screener.fetch_documents = MagicMock(return_value=[screener_link1, screener_link2, screener_link3])
    fetcher.nse.fetch_documents = MagicMock(return_value=[])

    docs = fetcher.fetch_documents("HDFCBANK", force_refresh=True)

    assert len(docs) == 3
    assert all(d.source_used == "SCREENER" for d in docs)
    fetcher.bse.fetch_documents.assert_called_once()
    fetcher.screener.fetch_documents.assert_called_once()
    fetcher.nse.fetch_documents.assert_not_called()


def test_3_tier_fallback_tier3_called_when_tier1_and_tier2_empty(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    nse_doc = UnifiedDocument(
        symbol="HDFCBANK",
        quarter="Q1 FY26",
        title="NSE Transcript Announcement",
        url="https://nselive.nseindia.com/content/t3.pdf",
        source_used="NSE",
        category="transcript",
    )

    fetcher.bse.fetch_documents = MagicMock(return_value=[])
    fetcher.screener.fetch_documents = MagicMock(return_value=[])
    fetcher.nse.fetch_documents = MagicMock(return_value=[nse_doc])

    docs = fetcher.fetch_documents("HDFCBANK", force_refresh=True)

    assert len(docs) == 1
    assert docs[0].source_used == "NSE"
    fetcher.bse.fetch_documents.assert_called_once()
    fetcher.screener.fetch_documents.assert_called_once()
    fetcher.nse.fetch_documents.assert_called_once()


def test_cross_source_deduplication(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    doc_bse = UnifiedDocument(
        symbol="RELIANCE",
        quarter="Q1 FY26",
        title="Reliance Concall Transcript Q1 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/rel_bse.pdf",
        source_used="BSE",
        category="transcript",
    )

    doc_screener = UnifiedDocument(
        symbol="RELIANCE",
        quarter="Q1 FY26",
        title="Reliance Concall Transcript Q1 FY26",
        url="https://www.screener.in/transcripts/rel_scr.pdf",
        source_used="SCREENER",
        category="transcript",
    )

    deduped = fetcher.deduplicate_documents([doc_screener, doc_bse])
    assert len(deduped) == 1
    assert deduped[0].source_used == "BSE"


@patch("requests.get")
def test_local_document_persistence(mock_get, tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    fake_pdf_content = b"%PDF-1.4 Mock Concall Transcript Bytes Data"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_pdf_content
    mock_get.return_value = mock_resp

    doc = UnifiedDocument(
        symbol="INFY",
        quarter="Q1 FY26",
        title="Infosys Concall Transcript Q1 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/infy_q1fy26.pdf",
        source_used="BSE",
        category="transcript",
    )

    stored_doc = fetcher.download_and_store(doc)

    assert stored_doc.extraction_status == "success"
    assert stored_doc.local_path is not None
    assert Path(stored_doc.local_path).exists()
    assert stored_doc.checksum == hashlib.md5(fake_pdf_content).hexdigest()
    assert stored_doc.file_size_bytes == len(fake_pdf_content)

    # Check database index
    db_records = db_store.get_documents_by_symbol_and_quarter("INFY", "Q1 FY26")
    assert len(db_records) == 1
    assert db_records[0]["checksum"] == stored_doc.checksum
    assert db_records[0]["source_used"] == "BSE"


def test_sqlite_indexing(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)

    doc = UnifiedDocument(
        symbol="TCS",
        quarter="Q4 FY25",
        title="TCS Investor Presentation Q4 FY25",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/tcs_q4fy25.pdf",
        source_used="BSE",
        category="presentation",
        bse_scrip_code="532540",
    )

    doc_id = db_store.save_document_index(doc)
    assert doc_id is not None

    indexed_by_q = db_store.get_documents_by_symbol_and_quarter("TCS", "Q4 FY25")
    assert len(indexed_by_q) == 1
    assert indexed_by_q[0]["title"] == "TCS Investor Presentation Q4 FY25"
    assert indexed_by_q[0]["category"] == "presentation"

    all_indexed = db_store.get_documents_index(symbol="TCS")
    assert len(all_indexed) == 1
    assert all_indexed[0]["bse_scrip_code"] == "532540"


def test_deduplicate_documents_distinct_filings_same_quarter_category(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    doc1 = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Concall Transcript Q3 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/concall_q3.pdf",
        source_used="BSE",
        category="transcript",
    )
    doc2 = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Analyst Meet Transcript Q3 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/analyst_q3.pdf",
        source_used="BSE",
        category="transcript",
    )
    doc3_duplicate = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Concall Transcript Q3 FY26",
        url="https://www.screener.in/transcripts/concall_q3.pdf",
        source_used="SCREENER",
        category="transcript",
    )

    deduped = fetcher.deduplicate_documents([doc1, doc2, doc3_duplicate])

    assert len(deduped) == 2
    titles = [d.title for d in deduped]
    assert "Concall Transcript Q3 FY26" in titles
    assert "Analyst Meet Transcript Q3 FY26" in titles


@patch("requests.get")
def test_download_and_store_pdf_magic_byte_validation(mock_get, tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    # Test 1: HTML content when PDF expected (Soft-404 / Error HTML page)
    mock_resp_html = MagicMock()
    mock_resp_html.status_code = 200
    mock_resp_html.content = b"<html><body>404 Not Found or Access Denied</body></html>"
    mock_get.return_value = mock_resp_html

    doc_invalid = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Concall Transcript",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/invalid.pdf",
        source_used="BSE",
        category="transcript",
    )

    res_invalid = fetcher.download_and_store(doc_invalid)
    assert res_invalid.extraction_status == "failed"
    assert res_invalid.local_path is None

    # Test 2: Valid PDF content with %PDF- header
    mock_resp_pdf = MagicMock()
    mock_resp_pdf.status_code = 200
    mock_resp_pdf.content = b"%PDF-1.5 Valid PDF Stream Data Here"
    mock_get.return_value = mock_resp_pdf

    doc_valid = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Concall Transcript",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/valid.pdf",
        source_used="BSE",
        category="transcript",
    )

    res_valid = fetcher.download_and_store(doc_valid)
    assert res_valid.extraction_status == "success"
    assert res_valid.local_path is not None
    assert Path(res_valid.local_path).exists()


def test_fallback_not_short_circuited_when_tier1_partial(tmp_path):
    db_path = tmp_path / "test.db"
    db_store = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db_store, docs_base_dir=tmp_path / "documents")

    bse_res_only = UnifiedDocument(
        symbol="TATAMOTORS",
        quarter="Q3 FY26",
        title="Financial Results Q3 FY26",
        url="https://www.bseindia.com/xml-data/corpfiling/AttachLive/res.pdf",
        source_used="BSE",
        category="financial_results",
    )

    screener_transcript = DocumentLink(
        title="Concall Transcript Q3 FY26",
        url="https://www.screener.in/transcripts/concall.pdf",
        category="transcript",
        date_hint="Q3 FY26",
    )
    screener_presentation = DocumentLink(
        title="Investor Presentation Q3 FY26",
        url="https://www.screener.in/presentations/ppt.pdf",
        category="presentation",
        date_hint="Q3 FY26",
    )

    fetcher.bse.fetch_documents = MagicMock(return_value=[bse_res_only])
    fetcher.screener.fetch_documents = MagicMock(return_value=[screener_transcript, screener_presentation])
    fetcher.nse.fetch_documents = MagicMock(return_value=[])

    docs = fetcher.fetch_documents("TATAMOTORS", force_refresh=True)

    fetcher.bse.fetch_documents.assert_called_once()
    fetcher.screener.fetch_documents.assert_called_once()

    categories = {d.category for d in docs}
    assert "financial_results" in categories
    assert "transcript" in categories
    assert "presentation" in categories


@patch("requests.get")
def test_screener_bse_scrip_code_fallback(mock_get):
    from providers.screener_provider import ScreenerProvider

    provider = ScreenerProvider()

    def side_effect(url, headers, timeout):
        resp = MagicMock()
        if "company/TATAMOTORS/" in url:
            resp.status_code = 404
            resp.text = "404 Not Found"
        elif "company/500570/" in url:
            resp.status_code = 200
            resp.text = """
            <section id="documents">
                <div class="documents sub">
                    <h3>Concall Transcripts</h3>
                    <ul>
                        <li><div>Nov 2025</div><a href="/transcripts/t.pdf">Transcript</a></li>
                    </ul>
                </div>
            </section>
            """
        else:
            resp.status_code = 404
        return resp

    mock_get.side_effect = side_effect

    links = provider.fetch_documents("TATAMOTORS")
    assert len(links) == 1
    assert links[0].category == "transcript"
    assert "https://www.screener.in/transcripts/t.pdf" in links[0].url

