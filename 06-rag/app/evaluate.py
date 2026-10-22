"""Score the RAG pipeline against eval/golden.yaml.

retrieval hit: an expected topic is among the retrieved chunks
grounded:      a named condition is exactly the title of an excerpt it cites
answer hit:    an expected topic is among the grounded conditions
"""
import requests
import yaml

API = "http://api:8000/ask"
cases = yaml.safe_load(open("/eval/golden.yaml"))

totals = {"retrieval": 0, "answer": 0, "grounded": 0, "named": 0}
print(f"{'case':<62} {'retr':>4} {'ans':>4} {'grnd':>5} {'stop':>6}  answer")
for case in cases:
    out = requests.post(API, json={"symptoms": case["symptoms"]}, timeout=600).json()
    retrieved = {r["title"] for r in out["retrieved"]}
    named = [c["name"] for c in out["conditions"]]
    grounded = [c["name"] for c in out["conditions"]
                if any(c["name"].lower() == s["title"].lower() for s in c["sources"])]

    expected = {e.lower() for e in case["expected"]}
    r_hit = bool(expected & {t.lower() for t in retrieved})
    a_hit = bool(expected & {g.lower() for g in grounded})
    totals["retrieval"] += r_hit
    totals["answer"] += a_hit
    totals["grounded"] += len(grounded)
    totals["named"] += len(named)
    print(f"{case['symptoms'][:60]:<62} {'yes' if r_hit else 'NO':>4} {'yes' if a_hit else 'NO':>4} "
          f"{len(grounded)}/{len(named):<3} {out['generation']['done_reason']:>6}  {', '.join(named[:3])}")

n = len(cases)
print(f"\nretrieval hit {totals['retrieval']}/{n} · answer hit {totals['answer']}/{n} · "
      f"grounded {totals['grounded']}/{totals['named']} named conditions")
