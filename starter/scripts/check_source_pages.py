"""Re-extract every PDF page and record inclusion, empties and failures.

This is a post-run source audit, not a fabricated original ingestion log.
It never changes the frozen corpus or benchmark.
"""
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pypdf import PdfReader
from src.ingestion import normalize_text

ROOT = Path(__file__).resolve().parents[2]
RANGES = [(93, 103), (105, 110), (111, 124), (125, 136), (137, 146)]


def main():
    path = ROOT / 'data/raw/thinkpython2.pdf'
    corpus = {p['page']: p for p in json.loads((ROOT / 'data/processed/corpus.json').read_text(encoding='utf-8'))}
    reader = PdfReader(path)
    rows = []
    failures = []
    for number, page in enumerate(reader.pages, 1):
        try:
            text = normalize_text(page.extract_text(extraction_mode='layout') or '')
            nonspace = len(re.sub(r'\s+', '', text))
            in_scope = any(lo <= number <= hi for lo, hi in RANGES)
            selected = in_scope and nonspace >= 500
            reason = ('selected_content' if selected else 'empty_page' if not text
                      else 'outside_chapters_8_to_12' if not in_scope else 'below_500_nonwhitespace_characters')
            matches = number in corpus and corpus[number]['text'] == text
            if selected != (number in corpus) or (selected and not matches):
                failures.append(f'Corpus mismatch on page {number}')
            rows.append(dict(page=number, extraction_status='ok', selected=int(selected),
                             char_count=len(text), nonwhitespace_count=nonspace, reason=reason,
                             corpus_text_matches=int(matches) if selected else 'N/A', error=''))
        except Exception as exc:
            failures.append(f'Page {number}: {type(exc).__name__}: {exc}')
            rows.append(dict(page=number, extraction_status='error', selected=0,
                             char_count=0, nonwhitespace_count=0, reason='extraction_failed',
                             corpus_text_matches='N/A', error=str(exc)))
    out = ROOT / 'results'
    out.mkdir(exist_ok=True)
    with (out / 'page_processing_log.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(checked_at=datetime.now(timezone.utc).isoformat(),
                   provenance='Post-run re-extraction audit; original run timings unchanged',
                   pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   total_pages=len(rows), selected_pages=sum(r['selected'] for r in rows),
                   skipped_pages=sum(not r['selected'] for r in rows),
                   empty_pages=sum(r['reason']=='empty_page' for r in rows),
                   extraction_errors=sum(r['extraction_status']=='error' for r in rows),
                   failures=failures)
    (out / 'page_processing_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit('Source page audit failed; see page_processing_log.csv')


if __name__ == '__main__':
    main()
