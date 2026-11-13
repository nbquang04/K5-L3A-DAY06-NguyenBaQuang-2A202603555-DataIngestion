"""Conservative exact-evidence proxy; never generates human labels."""
import re

def compact(text):
    return re.sub(r'\s+', '', text)

def evaluate_query(question, hits):
    labels = []
    for h in hits:
        golds = [question] + question.get('alternative_evidence', [])
        labels.append(any(h['metadata']['document_id']==g['gold_source_id'] and h['metadata']['page']==g['gold_page'] and compact(g['evidence_quote']) in compact(h['text']) for g in golds))
    return dict(question=question,hits=hits,evidence_matches=labels,hit1=bool(labels and labels[0]),hit3=any(labels))

def summarize(traces):
    result = []
    for strategy in sorted({t['strategy'] for t in traces}):
        for split in sorted({t['question']['split'] for t in traces}):
            rows = [t for t in traces if t['strategy']==strategy and t['question']['split']==split]
            if rows:
                result.append(dict(strategy=strategy,split=split,n=len(rows),hit1_count=sum(t['hit1'] for t in rows),hit3_count=sum(t['hit3'] for t in rows),hit1=sum(t['hit1'] for t in rows)/len(rows),hit3=sum(t['hit3'] for t in rows)/len(rows)))
    return result
