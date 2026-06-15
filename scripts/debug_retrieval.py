"""Debug script: check if Section 370 docs are indexed and retrievable."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from services.retrieval.bm25_store import BM25Store
from services.retrieval.search import hybrid_search
from services.api.database import SessionLocal
from services.api.models import Judgment

# 1. BM25 check
bm25 = BM25Store()
total = len(bm25._data.doc_ids) if bm25._data else 0
print(f"BM25 total chunks: {total}")

results = bm25.search("Section 370 IPC human trafficking", n=5)
print(f"\nBM25 results for 'Section 370 IPC human trafficking':")
for r in results:
    print(f"  doc_id={r['doc_id']} score={r['score']:.3f} | {r['text'][:80]}")

# 2. DB check
db = SessionLocal()
total_db = db.query(Judgment).count()
print(f"\nDB total judgments: {total_db}")

rows = db.query(Judgment.doc_id, Judgment.case_name, Judgment.acts_cited).all()
s370_rows = [(r.doc_id, r.case_name, r.acts_cited) for r in rows if r.acts_cited and "370" in str(r.acts_cited)]
print(f"DB rows mentioning 370 in acts_cited: {len(s370_rows)}")
for doc_id, name, acts in s370_rows[:3]:
    print(f"  {doc_id} | {name[:50]} | {str(acts)[:60]}")

# 3. Full hybrid search
print("\nHybrid search results for 'what is section 370':")
chunks = hybrid_search("what is section 370", statute_refs=["Section 370 IPC"], strategy="BM25_FIRST", top_k=5)
for c in chunks:
    print(f"  doc_id={c.doc_id} score={c.score:.3f} | {c.text[:80]}")

db.close()
