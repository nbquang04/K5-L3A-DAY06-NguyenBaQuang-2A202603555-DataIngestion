import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from starter.src.chunking import fixed_size,by_paragraph
from starter.src.models import DocumentPage
from starter.src.evaluation import evaluate_query
pages=[DocumentPage(**p) for p in json.loads(Path('data/processed/corpus.json').read_text(encoding='utf-8'))]
for p in pages:
    b=by_paragraph(p,1000)
    assert ''.join(c.text for c in b)==p.text
    for c in fixed_size(p,500,50)+b:
        assert c.text==p.text[c.metadata['start']:c.metadata['end']]
        assert len(c.text)<=1000
q=json.loads(Path('benchmark/questions.json').read_text(encoding='utf-8'))
assert len([x for x in q if x['filter']])>=3
assert any(x['split']=='test' and x['filter'] for x in q)
for item in q:
    p=next(p for p in pages if p.page==item['gold_page'])
    good=dict(metadata=dict(document_id=p.document_id,page=p.page),text=p.text)
    assert evaluate_query(item,[good])['hit1']
    bad=dict(metadata=dict(document_id=p.document_id,page=p.page),text='unrelated')
    assert not evaluate_query(item,[bad])['hit3']
print('PASS: chunk coverage/offsets, split/filter requirements, positive and negative evidence cases.')
