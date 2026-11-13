import hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from dotenv import load_dotenv
import psycopg
sys.path.insert(0,str(Path('starter').resolve()))
from src.embeddings import MyEmbedder,MODEL_REVISION
root=Path('.').resolve(); cache=root/'.cache/models'; model_cache=cache/'models--sentence-transformers--all-MiniLM-L6-v2'
assert (model_cache/'refs/main').read_text().strip()==MODEL_REVISION
snapshot=model_cache/'snapshots'/MODEL_REVISION
assert snapshot.is_dir()
model=MyEmbedder('sentence-transformers/all-MiniLM-L6-v2',str(cache))
load_dotenv(root/'starter/.env')
checks=[]
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
 for strategy in ['A','B']:
  cid,text=conn.execute('SELECT chunk_id,text FROM thinkpython_chunks WHERE strategy=%s ORDER BY chunk_id LIMIT 1',(strategy,)).fetchone()
  vector=model.embed_query(text)
  distance=conn.execute('SELECT embedding <=> %s::vector FROM thinkpython_chunks WHERE strategy=%s AND chunk_id=%s',('['+','.join(map(str,vector))+']',strategy,cid)).fetchone()[0]
  assert abs(distance)<1e-5,(strategy,distance)
  checks.append(dict(strategy=strategy,chunk_id=cid,cosine_distance=distance))
proof=dict(verified_at=datetime.now(timezone.utc).isoformat(),model='sentence-transformers/all-MiniLM-L6-v2',revision=MODEL_REVISION,provenance='Recovered after original runs from downloaded cache refs/main and snapshot; verified pinned model against one stored document vector per index. Not an original timestamped revision capture.',stored_vector_checks=checks,files=[dict(path=str(p.relative_to(snapshot)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in snapshot.rglob('*') if p.is_file()])
(root/'results/model_provenance.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
for name in ['run_dev.json','run_test.json']:
 p=root/'results'/name; obj=json.loads(p.read_text()); obj['model_revision']=MODEL_REVISION; obj['model_revision_provenance']='Recovered post-run from cache and verified; see model_provenance.json'; p.write_text(json.dumps(obj,indent=2),encoding='utf-8')
print('PASS: pinned revision loaded and agrees with stored A/B vectors; original metrics/timestamps unchanged.')
