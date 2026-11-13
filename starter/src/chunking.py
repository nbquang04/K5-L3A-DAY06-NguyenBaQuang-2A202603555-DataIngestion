"""Page-local fixed and paragraph chunking with offsets."""
import hashlib
import re
from .models import Chunk

def make_chunk(page, start, end, kind):
    text = page.text[start:end]
    key = f'{page.document_id}:{page.page}:{kind}:{start}:{end}:{text}'
    return Chunk(hashlib.sha256(key.encode()).hexdigest()[:24], page.document_id,
                 page.source, page.page, text, {**page.metadata, 'start': start, 'end': end})

def fixed_size(page, size, overlap):
    if not 0 <= overlap < size:
        raise ValueError('Require 0 <= overlap < size')
    chunks = []
    for start in range(0, len(page.text), size-overlap):
        chunks.append(make_chunk(page, start, min(start+size, len(page.text)), 'fixed'))
        if start+size >= len(page.text):
            break
    return chunks

def by_paragraph(page, max_size):
    if max_size <= 0:
        raise ValueError('max_size must be positive')
    boundaries = [m.end() for m in re.finditer(r'\n\s*\n', page.text)] + [len(page.text)]
    chunks, start = [], 0
    while start < len(page.text):
        ends = [b for b in boundaries if start < b <= start+max_size]
        end = max(ends) if ends else min(start+max_size, len(page.text))
        if not ends and end < len(page.text):
            line_end = page.text.rfind('\n', start+max_size//2, end)
            if line_end > start:
                end = line_end+1
        chunks.append(make_chunk(page, start, end, 'paragraph'))
        start = end
    return chunks
