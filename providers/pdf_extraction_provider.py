"""
Ground-Truth PDF Metric Extraction Provider.
Parses Investor Presentation PDFs and BSE/NSE Quarterly Financial Result Announcement PDFs
using PyPDF (pypdf) and structured table/regex parsers with financial unit normalization.
"""
import io
import re
import datetime
from pathlib import Path
from typing import Optional, Union, BinaryIO, Any
import requests
import pypdf

from models.ground_truth import GroundTruthFinancials


class PDFGroundTruthExtractor:
    """
    Extracts ground-truth financial metrics from company PDFs (Investor Presentations, Financial Results).
    Normalizes units (Lakhs, Millions, USD) to INR Crores.
    """

    UNIT_SCALES = {
        "lakh": 0.01,
        "lakhs": 0.01,
        "lac": 0.01,
        "lacs": 0.01,
        "million": 0.1,
        "millions": 0.1,
        "mn": 0.1,
        "billion": 100.0,
        "billions": 100.0,
        "bn": 100.0,
        "thousand": 0.0001,
        "thousands": 0.0001,
        "th": 0.0001,
        "usd_million": 8.3,
        "usd_mn": 8.3,
        "usd": 8.3,
        "crore": 1.0,
        "crores": 1.0,
        "cr": 1.0,
    }

    def __init__(self, db_store: Optional[Any] = None):
        self.db_store = db_store

    def detect_unit_scale(self, text: str) -> float:
        """
        Detect unit scale of reported figures in text.
        Returns multiplier to convert values to INR Crores (Rs Cr).
        """
        text_sample = text[:15000].lower() if text else ""

        # Check for Lakhs / Lacs
        if re.search(r"(?:in|₹|rs\.?|inr)\s*(?:lakhs?|lacs?|lakh)\b", text_sample) or re.search(r"\b(?:in\s+lakhs?|in\s+lacs?|rs\.?\s*in\s*lakhs?)\b", text_sample):
            return 0.01
        # Check for Billions / Bn
        if re.search(r"(?:in|₹|rs\.?|inr)\s*(?:billions?|bn)\b", text_sample) or re.search(r"\b(?:in\s+billions?|in\s+bn|rs\.?\s*in\s*billions?)\b", text_sample):
            return 100.0
        # Check for Millions / Mn
        if re.search(r"(?:in|₹|rs\.?|inr)\s*(?:millions?|mn)\b", text_sample) or re.search(r"\b(?:in\s+millions?|in\s+mn|rs\.?\s*in\s*millions?)\b", text_sample):
            return 0.1
        # Check for USD / $ Millions
        if re.search(r"(?:in|\$|usd)\s*(?:millions?|mn)\b", text_sample) or re.search(r"\b(?:usd\s*mn|\$\s*mn|usd\s*million)\b", text_sample):
            return 8.3
        # Check for Thousands
        if re.search(r"(?:in|₹|rs\.?|inr)\s*(?:thousands?|th)\b", text_sample):
            return 0.0001
        # Check for Crores / Cr
        if re.search(r"(?:in|₹|rs\.?|inr)\s*(?:crores?|cr)\b", text_sample) or re.search(r"\b(?:in\s+crores?|in\s+cr|rs\.?\s*in\s*crores?)\b", text_sample):
            return 1.0

        # Default fallback is Crores (1.0)
        return 1.0

    def normalize_unit(self, value: float, unit: str = "cr") -> float:
        """
        Convert a raw numeric value to INR Crores based on unit name or scale key.
        """
        if value is None:
            return None
        unit_key = (unit or "").strip().lower()
        scale = self.UNIT_SCALES.get(unit_key, 1.0)
        return round(value * scale, 2)

    def extract_text_from_pdf(self, pdf_input: Union[str, Path, bytes, BinaryIO]) -> str:
        """
        Extract plain text from a PDF file path, URL, bytes, or file-like object using pypdf.
        """
        if not pdf_input:
            return ""

        # Case 1: Bytes
        if isinstance(pdf_input, bytes):
            stream = io.BytesIO(pdf_input)
            return self._read_pdf_stream(stream)

        # Case 2: BinaryIO / Stream
        if hasattr(pdf_input, "read"):
            return self._read_pdf_stream(pdf_input)

        # Case 3: Path object or string
        input_str = str(pdf_input)

        # Check if URL
        if input_str.startswith("http://") or input_str.startswith("https://"):
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                res = requests.get(input_str, headers=headers, timeout=15)
                res.raise_for_status()
                return self._read_pdf_stream(io.BytesIO(res.content))
            except Exception as err:
                print(f"[PDFExtractor] Error downloading PDF from {input_str}: {err}")
                return ""

        # Check if local file path exists
        pdf_path = Path(input_str)
        if pdf_path.exists() and pdf_path.is_file():
            try:
                with open(pdf_path, "rb") as f:
                    return self._read_pdf_stream(f)
            except Exception as err:
                print(f"[PDFExtractor] Error reading PDF file {pdf_path}: {err}")
                return ""

        # Fallback: Assume input_str is raw text content if not a valid file path or URL
        return input_str

    def _read_pdf_stream(self, stream: Any) -> str:
        """Internal helper to extract text from a PDF stream using pypdf."""
        try:
            reader = pypdf.PdfReader(stream)
            extracted = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted.append(text)
            return "\n".join(extracted)
        except Exception as err:
            print(f"[PDFExtractor] PyPDF read error: {err}")
            return ""

    def _clean_number(self, val_str: str) -> Optional[float]:
        """Convert messy extracted string into float, handling negative numbers and (1,200.00) loss figures."""
        if not val_str:
            return None
        s = val_str.strip()
        is_negative = False
        if s.startswith("(") or s.endswith(")") or s.startswith("-"):
            is_negative = True

        cleaned_str = s.replace("(", "").replace(")", "").replace("-", "").replace(",", "").strip()
        cleaned = re.sub(r"[^\d\.]", "", cleaned_str)
        if not cleaned or cleaned == ".":
            return None
        try:
            val = float(cleaned)
            if val == 0.0:
                return 0.0
            return -val if is_negative else val
        except ValueError:
            return None

    def extract_metrics_from_text(
        self,
        text: str,
        symbol: str = "",
        quarter: str = "",
        doc_type: str = "presentation",
        source_pdf_url: str = "",
        source_local_path: str = "",
        explicit_unit: Optional[str] = None,
    ) -> GroundTruthFinancials:
        """
        Parse metrics from text using structured regex & table parsing.
        Normalizes figures to INR Crores.
        """
        if not text:
            return GroundTruthFinancials(
                symbol=symbol,
                quarter=quarter,
                doc_type=doc_type,
                extraction_confidence=0.0,
                source_pdf_url=source_pdf_url,
                source_local_path=source_local_path,
            )

        # Detect unit scale
        if explicit_unit:
            unit_scale = self.UNIT_SCALES.get(explicit_unit.lower(), 1.0)
        else:
            unit_scale = self.detect_unit_scale(text)

        revenue_cr = None
        ebitda_cr = None
        pat_cr = None
        revenue_growth_pct = None
        ebitda_margin_pct = None
        pat_growth_pct = None
        capex_cr = None
        segment_results = []
        guidance_numbers = {}

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Extract Revenue
        rev_patterns = [
            r"(?:revenue\s+from\s+operations|total\s+revenue|net\s+revenue|net\s+sales|total\s+income|income\s+from\s+operations)\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"(?:revenue|sales)\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"(?:revenue|total\s+revenue|net\s+revenue|sales|income)\s+(?:from\s+operations\s+)?(?:stood\s+at|reached|recorded\s+at|came\s+in\s+at|was|were|reported\s+at)\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
        ]
        for pat in rev_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                num = self._clean_number(m.group(1))
                if num is not None and num != 0:
                    scale = unit_scale
                    if len(m.groups()) >= 2 and m.group(2):
                        unit_key = m.group(2).lower()
                        scale = self.UNIT_SCALES.get(unit_key, unit_scale)
                    revenue_cr = round(num * scale, 2)
                    break

        # 2. Extract EBITDA
        ebitda_patterns = [
            r"(?:operating\s+ebitda|ebitda|operating\s+profit|pbdt)\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"\bebitda\b\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"(?:ebitda|operating\s+ebitda|operating\s+profit)\s+(?:stood\s+at|reached|recorded\s+at|came\s+in\s+at|was|were|reported\s+at)\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
        ]
        for pat in ebitda_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                num = self._clean_number(m.group(1))
                if num is not None:
                    scale = unit_scale
                    if len(m.groups()) >= 2 and m.group(2):
                        unit_key = m.group(2).lower()
                        scale = self.UNIT_SCALES.get(unit_key, unit_scale)
                    ebitda_cr = round(num * scale, 2)
                    break

        # 3. Extract PAT / Net Profit
        pat_patterns = [
            r"(?:pat|profit\s+after\s+tax|net\s+profit|profit\s+for\s+the\s+period)\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"\bpat\b\s*[:\-\|]?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            r"(?:pat|profit\s+after\s+tax|net\s+profit)\s+(?:stood\s+at|reached|recorded\s+at|came\s+in\s+at|was|were|reported\s+at)\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
        ]
        for pat in pat_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                num = self._clean_number(m.group(1))
                if num is not None:
                    scale = unit_scale
                    if len(m.groups()) >= 2 and m.group(2):
                        unit_key = m.group(2).lower()
                        scale = self.UNIT_SCALES.get(unit_key, unit_scale)
                    pat_cr = round(num * scale, 2)
                    break

        # 4. Extract Growth & Margin Percentages
        rev_growth_m = re.search(
            r"(?:revenue|sales|income)\s*(?:yoy)?\s*growth\s*[:\-\|]?\s*([\+\-]?[\d,]+\.?\d*)\s*%",
            text, re.IGNORECASE
        ) or re.search(
            r"(?:revenue\s+up\s+by|sales\s+grew\s+by)\s*([\+\-]?[\d,]+\.?\d*)\s*%",
            text, re.IGNORECASE
        )
        if rev_growth_m:
            revenue_growth_pct = self._clean_number(rev_growth_m.group(1))

        ebitda_margin_m = re.search(
            r"(?:ebitda|operating)\s*margin\s*[:\-\|]?\s*([\+\-]?[\d,]+\.?\d*)\s*%",
            text, re.IGNORECASE
        )
        if ebitda_margin_m:
            ebitda_margin_pct = self._clean_number(ebitda_margin_m.group(1))
        elif ebitda_cr is not None and revenue_cr is not None and revenue_cr > 0:
            ebitda_margin_pct = round((ebitda_cr / revenue_cr) * 100.0, 2)

        pat_growth_m = re.search(
            r"(?:pat|net\s+profit)\s*(?:yoy)?\s*growth\s*[:\-\|]?\s*([\+\-]?[\d,]+\.?\d*)\s*%",
            text, re.IGNORECASE
        ) or re.search(
            r"(?:pat\s+up\s+by|profit\s+grew\s+by)\s*([\+\-]?[\d,]+\.?\d*)\s*%",
            text, re.IGNORECASE
        )
        if pat_growth_m:
            pat_growth_pct = self._clean_number(pat_growth_m.group(1))

        # 5. Extract Capex
        capex_m = re.search(
            r"(?:capex|capital\s+expenditure|capex\s+spent|capex\s+incurred)\s*(?:[:\-\|]|stood\s+at|reached|recorded\s+at|came\s+in\s+at)?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)\s*(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)?",
            text, re.IGNORECASE
        )
        if capex_m:
            num = self._clean_number(capex_m.group(1))
            if num is not None:
                scale = unit_scale
                if len(capex_m.groups()) >= 2 and capex_m.group(2):
                    unit_key = capex_m.group(2).lower()
                    scale = self.UNIT_SCALES.get(unit_key, unit_scale)
                capex_cr = round(num * scale, 2)

        # 6. Extract Segment Results
        segment_lines = [
            line for line in lines
            if re.search(r"\b(?:segment|division|business\s+unit)\b", line, re.IGNORECASE)
            and re.search(r"[\d\.]+", line)
        ]
        for s_line in segment_lines[:10]:
            # Look for "Segment Name: 120 Cr" or "Segment Name | Revenue: 120"
            s_match = re.search(
                r"([A-Za-z0-9\s\&]+?)\s*[:\-\|]\s*(?:revenue\s*[:\-\|]?)?\s*(?:rs\.?|₹|\$)?\s*(\(?-?[\d,]+\.?\d*\)?)",
                s_line, re.IGNORECASE
            )
            if s_match:
                s_name = s_match.group(1).strip()
                s_val = self._clean_number(s_match.group(2))
                if s_name and s_val is not None and s_val > 0:
                    segment_results.append({
                        "name": s_name,
                        "revenue_cr": round(s_val * unit_scale, 2),
                    })

        # 7. Extract Guidance Numbers
        guidance_keys = {
            "revenue_guidance": r"(?:revenue|sales)\s*guidance\s*[:\-\|]?\s*([^\n\.\;]+)",
            "margin_guidance": r"(?:margin|ebitda)\s*guidance\s*[:\-\|]?\s*([^\n\.\;]+)",
            "capex_guidance": r"(?:capex|capital\s+expenditure)\s*guidance\s*[:\-\|]?\s*([^\n\.\;]+)",
        }
        for g_key, g_pat in guidance_keys.items():
            g_m = re.search(g_pat, text, re.IGNORECASE)
            if g_m:
                guidance_numbers[g_key] = g_m.group(1).strip()

        # Calculate Extraction Confidence (0.0 to 1.0)
        found_metrics = [m for m in (revenue_cr, ebitda_cr, pat_cr) if m is not None]
        confidence = round(len(found_metrics) / 3.0, 2)
        if confidence == 0.0 and (revenue_growth_pct is not None or ebitda_margin_pct is not None or segment_results):
            confidence = 0.33

        extracted_at_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        gt_obj = GroundTruthFinancials(
            symbol=symbol,
            quarter=quarter,
            doc_type=doc_type,  # 'presentation' or 'financial_results'
            revenue_cr=revenue_cr,
            ebitda_cr=ebitda_cr,
            pat_cr=pat_cr,
            revenue_growth_pct=revenue_growth_pct,
            ebitda_margin_pct=ebitda_margin_pct,
            pat_growth_pct=pat_growth_pct,
            segment_results=segment_results,
            capex_cr=capex_cr,
            guidance_numbers=guidance_numbers,
            extraction_confidence=confidence,
            extracted_at=extracted_at_str,
            source_pdf_url=source_pdf_url,
            source_local_path=source_local_path,
        )

        return gt_obj

    def extract_from_pdf(
        self,
        pdf_input: Union[str, Path, bytes, BinaryIO],
        symbol: str = "",
        quarter: str = "",
        doc_type: str = "presentation",
        source_pdf_url: str = "",
        source_local_path: str = "",
        explicit_unit: Optional[str] = None,
    ) -> GroundTruthFinancials:
        """
        Extract ground-truth financials directly from a PDF file/stream/URL.
        Optionally saves to SQLite if db_store was provided at init.
        """
        local_path = source_local_path
        if not local_path and isinstance(pdf_input, (str, Path)):
            p = Path(pdf_input)
            if p.exists() and p.is_file():
                local_path = str(p.resolve())

        text = self.extract_text_from_pdf(pdf_input)
        gt = self.extract_metrics_from_text(
            text=text,
            symbol=symbol,
            quarter=quarter,
            doc_type=doc_type,
            source_pdf_url=source_pdf_url,
            source_local_path=local_path,
            explicit_unit=explicit_unit,
        )

        if self.db_store and hasattr(self.db_store, "save_ground_truth"):
            self.db_store.save_ground_truth(gt)

        return gt
