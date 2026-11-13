"""Prepare a frozen, source-verified corpus and benchmark before retrieval."""
import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ingestion import load_pdf
ROOT = Path(__file__).resolve().parents[2]
def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    target = ROOT/'benchmark/questions.json'
    if target.exists():
        raise SystemExit('Benchmark already frozen; refusing to overwrite.')
    pdf = ROOT/'data/raw/thinkpython2.pdf'
    pages = load_pdf(pdf, 'thinkpython2', 'data/raw/thinkpython2.pdf')
    ranges = [(93,103,'Strings'),(105,110,'Word play'),(111,124,'Lists'),(125,136,'Dictionaries'),(137,146,'Tuples')]
    selected = []
    for p in pages:
        for lo,hi,chapter in ranges:
            if lo <= p.page <= hi and len(re.sub(r'\s+','',p.text)) >= 500:
                p.metadata = dict(chapter=chapter,version='2nd edition, 2.4.1',language='en')
                selected.append(p)
    assert len(selected)>=30
    write(ROOT/'data/processed/corpus.json', [asdict(p) for p in selected])
    write(ROOT/'data/manifest.json', dict(source_id='thinkpython2',title='Think Python, 2nd Edition, Version 2.4.1',author='Allen B. Downey',source_path_or_url='https://greenteapress.com/thinkpython2/thinkpython2.pdf',license_or_permission='CC BY-NC 3.0; retain attribution and license; noncommercial educational use',license_url='https://creativecommons.org/licenses/by-nc/3.0/',accessed_at=datetime.fromtimestamp(pdf.stat().st_mtime, timezone.utc).isoformat(),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),physical_page_count=len(pages),page_convention='1-based physical PDF pages',counting_rule='Chapters 8-12; exclude pages with fewer than 500 non-whitespace characters (blank/header-only pages). Include explanatory text and relevant exercises.',content_page_count=len(selected),pages=[dict(page=p.page,chapter=p.metadata['chapter'],char_count=len(p.text)) for p in selected],limitations='Layout extraction retains many paragraphs but may merge italic words, hyphenate words, or lose code indentation. Diagrams are not interpreted. Book describes an older Python version; benchmark asks about this source, not current Python behavior.'))
    seeds = [
      (93,'What is a string a sequence of?','Characters.','A string is a sequence of characters.',None),
      (93,'What does an index indicate in a sequence?','Which character in the sequence you want.','The index indicates which character',None),
      (95,'Does a string slice include its last boundary character?','It includes the first and excludes the last.','including the first but excluding the last.',None),
      (97,'What does the find function return if the character is absent?','-1.','If the character is not found, the function returns',None),
      (97,'In the Strings chapter, what does the upper method produce?','A new string with all uppercase letters.','a new string with all uppercase','Strings'),
      (111,'Can a list contain elements of different types?','Yes; elements need not be the same type.','The elements\nof a list',None),
      (111,'What is a list within another list called?','Nested.','A list within another list',None),
      (113,'Does a for loop over an empty list execute its body?','No.','loop over an empty list never runs the body:',None),
      (113,'What operator concatenates lists?','The + operator.','operator concatenates lists:',None),
      (115,'What built-in function adds up the elements of a list?','sum.','Adding up the elements of a list',None),
      (117,'In the Lists chapter, what does the split method do to a string?','Breaks it into words.','If you want to break a string into','Lists'),
      (125,'How many values is each dictionary key associated with?','A single value.','Each key is associated with a single value.',None),
      (126,'What happens when a dictionary lookup uses an absent key?','An exception is raised (KeyError in the example).','If the key',None),
      (127,'Why is a dictionary advantageous for counting letters?','You need not know all letters ahead of time and only allocate for letters present.','an advantage of the dictionary implementation',None),
      (131,'What is a memo in the Fibonacci discussion?','A previously computed value stored for later use.','A previously computed value',None),
      (137,'In the Tuples chapter, how do you create a one-element tuple?','Include a final comma.','To create a tuple with a single element','Tuples'),
      (139,'What must be true of the numbers of variables and values in tuple assignment?','They must be the same.','The number of variables on the left',None),
      (140,'What does a parameter beginning with an asterisk gather arguments into?','A tuple.','A parameter name that begins with',None),
      (141,'When zip receives sequences of unequal length, how long is the result?','As long as the shorter sequence.','If the sequences are not the same length',None),
      (142,'What can initialize a dictionary using tuples?','A list of key-value tuples.','you can use a list of tuples to initialize',None),
    ]
    questions=[]
    for i,(number,q,answer,marker,filt) in enumerate(seeds,1):
        p=next(p for p in selected if p.page==number)
        flat=re.sub(r'\s+',' ',p.text)
        marker=re.sub(r'\s+',' ',marker)
        # Match normalized whitespace, quote the complete containing sentence/block.
        start=flat.find(marker)
        if start<0:
            raise ValueError((i,marker))
        end=flat.find('.',start+len(marker))
        if marker.endswith('.'):
            end=start+len(marker)-1
        if end<0 or end-start>500:
            end=min(start+250,len(flat)-1)
        evidence=flat[start:end+1]
        questions.append(dict(id=f'q{i:02}',split='dev' if i<=15 else 'test',question=q,expected_answer=answer,gold_source_id='thinkpython2',gold_page=number,evidence_quote=evidence,filter={'chapter':filt} if filt else None,label_provenance='AI drafted; quote checked against extracted physical page; student review required'))
    spans = {
      'q03': ('The operator', 'it might help'),
      'q05': ('For example, the method', 'Instead of'),
      'q08': ('Aforloop over an empty list', 'Although a list'),
      'q09': ('The+operator concatenates lists:', '>>> a ='),
      'q10': ('Adding up the elements of a list', '>>> t ='),
      'q11': ('If you want to break a string into', '>>> s ='),
      'q13': ('If the key', 'Thelenfunction'),
      'q16': ('To create a tuple with a single element', '>>> t1'),
      'q17': ('The number of variables on the left', '>>> a, b'),
      'q20': ('you can use a list of tuples to initialize', '>>> t =')}
    for q in questions:
        if q['id'] in spans:
            a, b = spans[q['id']]
            text = re.sub(r'\s+', ' ', next(p.text for p in selected if p.page == q['gold_page']))
            start = text.index(a)
            q['evidence_quote'] = text[start:text.index(b, start + len(a))].strip()
    write(target,questions)
    write(ROOT/'benchmark/protocol.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),questions_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),selection_rule='Maximize dev exact-evidence Hit@3, then Hit@1, then lower chunk count; alphabetical tie-break. Freeze before test.',split='First 15 development, last 5 test; same book and topics, so topic leakage and small sample limit generalization.',coherence_sample='First ten selected physical pages, character position floor(page length / 2), chosen before retrieval.',human_review_status='Pending; AI-drafted benchmark and audit sheets require student review. Do not tune using test.'))
    print(f'Prepared {len(selected)} content pages and {len(questions)} frozen questions.')
if __name__=='__main__':
    main()
