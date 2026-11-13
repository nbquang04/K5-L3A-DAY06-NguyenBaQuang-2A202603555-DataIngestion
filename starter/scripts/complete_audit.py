"""Persist AI qualitative judgments and independently verify PDF metadata.

These are disclosed AI judgments, not student-authored human labels.
Scores below were assigned after reading each sampled chunk / test top-3.
Retrieval scores and the development selection are never changed here.
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pypdf import PdfReader
from src.ingestion import normalize_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results'
REVIEWER = 'Quảng'


def read_sheet(name):
    with (OUT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_sheet(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    coherence = read_sheet('audit_coherence.csv')
    # Preserve reviewer-confirmed labels and provenance on subsequent invocations.
    if any(row.get('review_status') == 'Confirmed by reviewer' for row in coherence):
        raise SystemExit('Audit already confirmed by reviewer; refusing to overwrite confirmed labels.')
    # Page 99 has two overlapping A chunks; both are individually reviewed.
    a_reasons = {
        93: 'Indexing and zero-based offset are understandable, but the opening string and final assignment are cut.',
        94: 'Traversal is defined, but the chunk starts mid-sentence and ends in an incomplete while-loop body.',
        95: 'Duckling loop and output are visible, but the opening explanation and closing correction instruction are cut.',
        96: 'String item assignment error is shown, but the definition of immutable and the repair are outside this chunk.',
        97: 'Counter loop and result explanation are intact; the heading and following exercise instruction are cut.',
        98: 'find examples are interpretable, but the start-index argument explanation is cut before its completion.',
        100: 'Printing indices is recognizable as a debugging technique; the function context and final exception text are incomplete.',
        101: 'Several glossary definitions are complete, but the preceding definition and following exercise URL are cut.',
        102: 'Several lowercase functions are complete, but the exercise prompt is missing and the following cipher definition is cut.',
    }
    b_labels = {
        93: (2, 'String sequence, bracket indexing, example and index definition form a complete standalone explanation.'),
        94: (2, 'len, the out-of-range error, length minus one and negative indexing are explained with complete examples; trailing heading adds no needed context.'),
        95: (1, 'Slice semantics are complete, but the opening loop lacks prefixes/suffix definitions and the final slice example has no output.'),
        96: (2, 'The failed assignment, immutability explanation and construction of a new string are all present.'),
        97: (2, 'The counting program, counter explanation and exercise instructions are complete; the find extension is explicitly referenced.'),
        98: (1, 'find start/stop arguments are explained, but word is not initialized in this chunk and the opening comparison depends on previous context.'),
        99: (2, 'String comparison examples, uppercase/lowercase ordering and lowercase normalization advice are complete.'),
        100: (1, 'The algorithm explanation is readable, but the function definition is missing and the debugging loop is incomplete.'),
        101: (2, 'Search, counter, invocation and optional-argument glossary entries are individually complete and understandable.'),
        102: (1, 'Cipher explanation is complete, but the opening lowercase functions lack their exercise prompt and interpretation.'),
    }
    for row in coherence:
        page = int(row['page'])
        if row['strategy'] == 'A':
            reason = a_reasons.get(page)
            if page == 99:
                reason = ('Comparison examples are readable, but the casing rule ends mid-sentence.'
                          if row['chunk_id'] == '4706e0aa031e343b563c88f8'
                          else 'Casing rule and normalization advice are readable; opening and following debugging sentence are truncated.')
            row.update(score=1, reason=reason, reviewer=REVIEWER)
        else:
            score, reason = b_labels[page]
            row.update(score=score, reason=reason, reviewer=REVIEWER)
    for row in coherence:
        row.update(label_author='Codex AI', review_status='AI-proposed; pending confirmation by reviewer')
    write_sheet('audit_coherence.csv', coherence)

    traces = json.loads((OUT / 'traces_test.json').read_text(encoding='utf-8'))
    lookup = {(t['strategy'], t['question']['id']): t for t in traces}
    # Semantic judgments of the retrieved set, not exact-quote matching.
    labels = {
        ('A', 'q16'): (2, 'Rank 1 on PDF page 137 explicitly requires a final comma and contrasts a singleton tuple with a parenthesized string.'),
        ('A', 'q17'): (2, 'Rank 1 on PDF page 139 explicitly says the numbers of variables and values must be the same, with the mismatched assignment example.'),
        ('A', 'q18'): (2, 'Rank 1 on PDF page 140 explicitly states that a starred parameter gathers arguments into a tuple and shows printall(*args).'),
        ('A', 'q19'): (1, 'The hits explain zip and pair iteration on pages 140-141, but omit the unequal-length rule and its shorter-sequence result.'),
        ('A', 'q20'): (1, 'Page 142 gives dictionary key-value tuples and page 143 discusses tuple keys, but no hit explains initializing dict from a list of pairs.'),
        ('B', 'q16'): (2, 'Rank 1 on PDF page 137 contains the singleton final-comma requirement, code and contrasting non-tuple example.'),
        ('B', 'q17'): (1, 'Page 144 defines tuple assignment, but none of the three hits states that the number of variables and values must match.'),
        ('B', 'q18'): (2, 'Rank 2 on PDF page 140 explicitly explains starred argument gathering into a tuple, with a complete example.'),
        ('B', 'q19'): (1, 'zip and iterator behavior are present on pages 140-141, but the essential unequal-length condition and shortest-length rule are absent.'),
        ('B', 'q20'): (0, 'Rank 1 is only a Dictionaries and tuples heading; the other hits describe tuple construction, not dictionary initialization from key-value pairs.'),
    }
    grounding = read_sheet('audit_grounding.csv')
    for row in grounding:
        strategy, qid = row['strategy'], row['question_id']
        if strategy == 'C':
            # Check actual content equality, rather than assume filter has no effect.
            assert [h['chunk_id'] for h in lookup[('B', qid)]['hits']] == [h['chunk_id'] for h in lookup[('C', qid)]['hits']]
        score, reason = labels[('B' if strategy == 'C' else strategy, qid)]
        row.update(score=score, reason=reason, reviewer=REVIEWER)
    for row in grounding:
        row.update(label_author='Codex AI', review_status='AI-proposed; pending confirmation by reviewer')
    write_sheet('audit_grounding.csv', grounding)

    reader = PdfReader(ROOT / 'data/raw/thinkpython2.pdf')
    extracted = {}
    chapters = {}
    current = None
    for number, page in enumerate(reader.pages, 1):
        text = normalize_text(page.extract_text(extraction_mode='layout') or '')
        extracted[number] = text
        match = re.match(r'Chapter\s+(8|9|10|11|12)\s*\n\s*([^\n]+)', text)
        if match:
            current = {'8': 'Strings', '9': 'Word play', '10': 'Lists',
                       '11': 'Dictionaries', '12': 'Tuples'}[match.group(1)]
        chapters[number] = current
    metadata = read_sheet('audit_metadata.csv')
    for row in metadata:
        trace = lookup[(row['strategy'], row['question_id'])]
        hit = trace['hits'][int(row['rank']) - 1]
        assert hit['chunk_id'] == row['chunk_id']
        m = hit['metadata']
        page = m['page']
        checks = {
            'document_id': m.get('document_id') == 'thinkpython2',
            'source': m.get('source') == 'data/raw/thinkpython2.pdf',
            'page_and_offsets': extracted[page][m['start']:m['end']] == hit['text'],
            'chapter': m.get('chapter') == chapters[page],
            'language': m.get('language') == 'en',
            'version': m.get('version') == '2nd edition, 2.4.1',
        }
        assert '2.4.1' in extracted[1]
        required = trace['question'].get('filter')
        compliant = all(m.get(k) == v for k, v in required.items()) if required else None
        row.update(complete_and_correct=int(all(checks.values())),
                   filter_compliant='N/A' if compliant is None else int(compliant),
                   reason=f'Checked against re-extracted physical PDF page {page}, chapter {chapters[page]}, exact text offsets, document path and cover version. '
                          + ('All metadata checks passed.' if all(checks.values()) else 'Failed: ' + ', '.join(k for k, v in checks.items() if not v)),
                   reviewer=REVIEWER, label_author='Codex AI',
                   review_status='AI-proposed; pending confirmation by reviewer')
    write_sheet('audit_metadata.csv', metadata)

    summary = {'reviewer': REVIEWER, 'label_author': 'Codex AI',
               'review_status': 'AI-proposed; pending confirmation by reviewer',
               'method': 'AI qualitative reading of all sampled chunks and test top-3; independent deterministic PDF metadata checks; no human review claimed.',
               'reviewed_at': datetime.now(timezone.utc).isoformat(),
               'limitations': 'Same AI assistant implemented pipeline and assessed it after seeing scores; not blind or independent. Source comparison uses extracted text, not visual PDF inspection. Student review remains recommended.',
               'strategies': []}
    for strategy in 'ABC':
        per_position = defaultdict(list)
        for r in coherence:
            if r['strategy'] == strategy:
                per_position[(r['page'], r['position'])].append(int(r['score']))
        g = [int(r['score']) for r in grounding if r['strategy'] == strategy]
        m = [r for r in metadata if r['strategy'] == strategy]
        filter_traces = [t for t in traces if t['strategy'] == strategy and t['question'].get('filter')]
        compliant_queries = sum(all(all(h['metadata'].get(k) == v for k, v in t['question']['filter'].items()) for h in t['hits']) for t in filter_traces)
        summary['strategies'].append(dict(strategy=strategy,
            coherence_mean=sum(sum(v)/len(v) for v in per_position.values())/len(per_position),
            coherence_positions=len(per_position), coherence_rows=sum(len(v) for v in per_position.values()),
            metadata_correct=sum(int(r['complete_and_correct']) for r in m), metadata_total=len(m),
            filter_compliant_queries=compliant_queries, filter_queries=len(filter_traces),
            grounding_counts={str(i): Counter(g)[i] for i in range(3)}, grounding_mean=sum(g)/len(g), grounding_n=len(g)))
    (OUT / 'audit_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
