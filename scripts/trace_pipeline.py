"""Trace the full pipeline for a query to show exactly what context the LLM sees."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from services.agents.pipeline import run_pipeline
from services.agents.verification_agent import _format_context

query = "what is section 370 IPC?"
print(f"Query: {query}")
print("="*60)

state = run_pipeline(query)

print(f"Status: {state.get('status')}")
print(f"Query type: {state.get('query_type')}")
print(f"Rewritten query: {state.get('rewritten_query', '-')}")
print(f"Statute refs: {state.get('statute_refs', [])}")
print()

chunks = state.get('traversal_results') or state.get('retrieved_chunks', [])
print(f"Retrieved chunks: {len(chunks)}")
for c in chunks:
    print(f"  doc_id={c.doc_id} score={c.score:.3f} | {c.text[:100]}")
print()

context = _format_context(chunks)
print("Context sent to LLM (first 800 chars):")
print(context[:800])
print()
print("Draft answer:")
print(state.get('draft_answer', '')[:400])
