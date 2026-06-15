"""Test all previously-failing definitional queries."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import httpx

queries = [
    "what is section 370?",
    "what is section 376 IPC?",
    "what is Article 21 of the Constitution?",
    "what is Section 302 IPC?",
    "what is Section 438 CrPC anticipatory bail?",
    "what is Section 498A IPC dowry cruelty?",
]

for q in queries:
    r = httpx.post("http://localhost:8080/api/v1/query", json={"query": q}, timeout=90)
    d = r.json()
    status = d.get("status")
    conf = round(d.get("confidence", 0), 2)
    cites = len(d.get("citations", []))
    ans = d.get("answer", "")
    failed = "could not find" in ans or "INSUFFICIENT" in ans
    result = "FAILS" if failed else "WORKS"
    print(f"[{result}] {q}")
    print(f"       {status} conf={conf} cites={cites}")
    if not failed:
        print(f"       {ans[:160].replace(chr(10), ' ')}")
    print()
