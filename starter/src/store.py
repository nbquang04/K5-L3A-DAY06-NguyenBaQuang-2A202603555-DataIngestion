"""Persistent pgvector store with exact cosine search."""
import math
import psycopg
from psycopg.types.json import Jsonb

class PgVectorStore:
    def __init__(self, database_url, dimensions):
        if not isinstance(dimensions, int) or not 0 < dimensions <= 2000:
            raise ValueError('Invalid dimensions')
        self.database_url, self.dimensions = database_url, dimensions

    def vector(self, values):
        if len(values) != self.dimensions or not all(math.isfinite(v) for v in values) or not any(values):
            raise ValueError('Invalid cosine vector')
        return '[' + ','.join(str(float(v)) for v in values) + ']'

    def create_schema(self):
        with psycopg.connect(self.database_url) as conn:
            conn.execute(f'CREATE TABLE IF NOT EXISTS thinkpython_chunks (strategy text NOT NULL, chunk_id text NOT NULL, text text NOT NULL, metadata jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL, PRIMARY KEY(strategy, chunk_id))')

    def upsert(self, strategy, chunks, vectors):
        if len(chunks) != len(vectors):
            raise ValueError('Chunk/vector count mismatch')
        rows = [(strategy, c.chunk_id, c.text, Jsonb({**c.metadata, 'document_id': c.document_id, 'source': c.source, 'page': c.page}), self.vector(v)) for c,v in zip(chunks,vectors)]
        # Transactionally replace complete strategy snapshot, including stale chunks.
        with psycopg.connect(self.database_url) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(606013)')
            conn.execute('DELETE FROM thinkpython_chunks WHERE strategy=%s', (strategy,))
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO thinkpython_chunks VALUES (%s,%s,%s,%s,%s::vector)', rows)

    def count(self, strategy):
        with psycopg.connect(self.database_url) as conn:
            return conn.execute('SELECT count(*) FROM thinkpython_chunks WHERE strategy=%s', (strategy,)).fetchone()[0]

    def search(self, strategy, query_vector, top_k=3, filters=None):
        filters = filters or {}
        if set(filters)-{'chapter','language','version'}:
            raise ValueError('Unsupported metadata filter')
        if top_k < 1:
            raise ValueError('top_k must be positive')
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute('SELECT chunk_id,text,metadata,1-(embedding <=> %s::vector) FROM thinkpython_chunks WHERE strategy=%s AND metadata @> %s ORDER BY embedding <=> %s::vector,chunk_id LIMIT %s', (self.vector(query_vector),strategy,Jsonb(filters),self.vector(query_vector),top_k)).fetchall()
        return [dict(chunk_id=r[0],text=r[1],metadata=r[2],score=r[3]) for r in rows]
