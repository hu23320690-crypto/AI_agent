"""Conservative, inspectable metrics. Keyword checks are not semantic accuracy."""
import math
import re
from pathlib import Path
from difflib import SequenceMatcher

def compact(text):
    return re.sub(r"\s+", "", text)

def evidence_coverage(quote, passages):
    gold = compact(quote)
    covered = set()
    for passage in passages:
        for block in SequenceMatcher(None, gold, compact(passage), autojunk=False).get_matching_blocks():
            # Isolated common Chinese words are not evidence.
            if block.size >= min(8, len(gold)):
                covered.update(range(block.a, block.a + block.size))
    return len(covered) / len(gold) if gold else 0.0

def retrieval_metrics(case, docs):
    if not case.get("evidence"):
        return None
    coverage = {}
    for k in (1, 3, 5):
        values = []
        for evidence in case["evidence"]:
            source = Path(evidence["source"]).name
            passages = [doc["text"] for doc in docs[:k] if Path(doc["metadata"].get("source", "")).name == source]
            values.append(evidence_coverage(evidence["quote"], passages))
        coverage[k] = max(values)
    rank = next((k for k in range(1, len(docs)+1)
                 if max(evidence_coverage(e["quote"], [d["text"] for d in docs[:k]
                        if Path(d["metadata"].get("source", "")).name == Path(e["source"]).name])
                        for e in case["evidence"]) >= 0.6), None)
    return {"evidence_coverage": {str(k):v for k,v in coverage.items()},
            "hit": {str(k):v >= 0.6 for k,v in coverage.items()},
            "reciprocal_rank_at_5": 1/rank if rank else 0.0,
            "definition": "命中=标注来源内的证据字符覆盖>=60%；来源精确匹配；非穷尽语义相关性标注。"}

def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values))-1)]

def tool_selection(turn, calls):
    names = {c["name"] for c in calls}
    required = set(turn["required_tools"])
    allowed = set(turn["allowed_tools"])
    return {"pass": required <= names and names <= allowed,
            "missing": sorted(required-names), "unexpected": sorted(names-allowed)}
