"""Extract physical PDF pages with layout retained."""
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from .models import DocumentPage

def normalize_text(text):
    text = unicodedata.normalize('NFC', text)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(x.rstrip() for x in text.splitlines())).strip()

def load_pdf(path, document_id, source):
    return [DocumentPage(document_id, source, i, normalize_text(p.extract_text(extraction_mode='layout') or ''))
            for i, p in enumerate(PdfReader(path).pages, 1)]
