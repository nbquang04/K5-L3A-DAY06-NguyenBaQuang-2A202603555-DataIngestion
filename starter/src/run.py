"""Development selection precedes held-out test; human labels stay blank."""
import argparse, csv, hashlib, importlib.metadata, json, os, platform, time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from .models import DocumentPage
from .chunking import fixed_size, by_paragraph
from .embeddings import MyEmbedder
from .store import PgVectorStore
from .evaluation import evaluate_query, summarize, compact
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results'
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sheet(name,rows):
    if (OUT/name).exists():
        return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--split',choices=['dev','test'],default='dev'); args=parser.parse_args()
    OUT.mkdir(exist_ok=True); load_dotenv(ROOT/'starter/.env')
    questions=json.loads((ROOT/'benchmark/questions.json').read_text(encoding='utf-8'))
    protocol=json.loads((ROOT/'benchmark/protocol.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256((ROOT/'benchmark/questions.json').read_bytes()).hexdigest()
    if digest!=protocol['questions_sha256']: raise ValueError('Benchmark modified after freezing')
    pages=[DocumentPage(**p) for p in json.loads((ROOT/'data/processed/corpus.json').read_text(encoding='utf-8'))]
    assert len(pages)>=30 and len({p.page for p in pages})==len(pages)
    for q in questions:
        p=next(p for p in pages if p.page==q['gold_page'])
        if compact(q['evidence_quote']) not in compact(p.text): raise ValueError(q['id'])
    config=dict(model='sentence-transformers/all-MiniLM-L6-v2',metric='cosine',search='exact',A=dict(size=500,overlap=50),B=dict(max_size=1000),C='B plus supplied chapter filter')
    config_hash=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    if args.split=='test':
        selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
        if selection['config_hash']!=config_hash or selection['benchmark_hash']!=digest: raise ValueError('Selection invalid')
    start=time.perf_counter(); embedder=MyEmbedder(config['model'],str(ROOT/'.cache/models'))
    store=PgVectorStore(os.environ['DATABASE_URL'],embedder.dimensions); store.create_schema()
    ca=[c for p in pages for c in fixed_size(p,500,50)]
    cb=[c for p in pages for c in by_paragraph(p,1000)]
    groups={'A':ca,'B':cb,'C':cb}; stats=[]
    if args.split=='dev':
        for strategy,chunks in [('A',ca),('B',cb)]:
            t=time.perf_counter(); vectors=embedder.embed_documents([c.text for c in chunks])
            store.upsert(strategy,chunks,vectors); before=store.count(strategy)
            store.upsert(strategy,chunks,vectors); assert before==store.count(strategy)==len(chunks)
            lengths=[len(c.text) for c in chunks]
            tokens=[len(embedder.model.tokenizer.encode(c.text)) for c in chunks]
            stats.append(dict(strategy=strategy,chunk_count=len(chunks),total_characters=sum(lengths),min_characters=min(lengths),max_characters=max(lengths),mean_characters=sum(lengths)/len(lengths),embedding_and_two_writes_seconds=time.perf_counter()-t,reingestion_count=store.count(strategy),total_tokens=sum(tokens),truncated_chunks=sum(n>embedder.model.max_seq_length for n in tokens)))
            save(f'chunks_{strategy}.json',[asdict(c) for c in chunks])
        save('ingestion_stats.json',stats); save('config.json',config)
    traces=[]
    for q in questions:
        if q['split']!=args.split: continue
        vector=embedder.embed_query(q['question'])
        for strategy in ['A','B','C']:
            filters=q['filter'] if strategy=='C' else None
            trace=evaluate_query(q,store.search('B' if strategy=='C' else strategy,vector,3,filters))
            trace.update(strategy=strategy,applied_filter=filters); traces.append(trace)
    save(f'traces_{args.split}.json',traces); summary=summarize(traces); save(f'metrics_{args.split}.json',summary)
    if args.split=='dev':
        winner=sorted(summary,key=lambda r:(-r['hit3'],-r['hit1'],len(groups[r['strategy']]),r['strategy']))[0]['strategy']
        save('selection.json',dict(strategy=winner,config_hash=config_hash,benchmark_hash=digest,selected_at=datetime.now(timezone.utc).isoformat(),rule=protocol['selection_rule'],test_used=False))
        rows=[]
        for p in pages[:10]:
            pos=len(p.text)//2
            for strategy,chunks in groups.items():
                for c in chunks:
                    if c.page==p.page and c.metadata['start']<=pos<c.metadata['end']:
                        rows.append(dict(strategy=strategy,page=p.page,position=pos,chunk_id=c.chunk_id,text=c.text,score='',reason='',reviewer=''))
        sheet('audit_coherence.csv',rows)
    else:
        sheet('audit_grounding.csv',[dict(strategy=t['strategy'],question_id=t['question']['id'],question=t['question']['question'],score='',reason='',reviewer='') for t in traces])
        sheet('audit_metadata.csv',[dict(strategy=t['strategy'],question_id=t['question']['id'],rank=i,chunk_id=h['chunk_id'],metadata=json.dumps(h['metadata']),complete_and_correct='',filter_compliant='',reason='',reviewer='') for t in traces for i,h in enumerate(t['hits'],1)])
    packages={n:importlib.metadata.version(n) for n in ['sentence-transformers','transformers','torch','pypdf','psycopg']}
    save(f'run_{args.split}.json',dict(timestamp=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),packages=packages,model=config['model'],dimensions=embedder.dimensions,max_sequence_length=embedder.model.max_seq_length,model_revision=embedder.revision,device='cpu',normalized_vectors=True,query_document_processing='same encode; no prefixes',seconds=time.perf_counter()-start,paid_api_cost=0,benchmark_sha256=digest,human_audit_status='see audit_summary.json'))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':
    try: main()
    except Exception as exc:
        OUT.mkdir(exist_ok=True)
        with (OUT/'errors.log').open('a',encoding='utf-8') as f: f.write(f'{datetime.now(timezone.utc).isoformat()} {type(exc).__name__}: {exc}\n')
        raise
