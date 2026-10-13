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


def context_metrics(case, docs):
    """Coverage of every annotated anchor in all documents actually sent."""
    policy = case.get("evidence_policy", "any")
    if policy not in ("any", "all"):
        raise ValueError("Unknown evidence_policy: " + str(policy))
    if not case.get("evidence"):
        return None
    basename = lambda value: str(value).replace("\\", "/").rsplit("/", 1)[-1]
    values = [evidence_coverage(e["quote"], [d["text"] for d in docs
              if basename(d["metadata"].get("source", "")) == basename(e["source"])])
              for e in case["evidence"]]
    return {"required_evidence_coverage": values,
            "any_hit": any(v >= 0.6 for v in values),
            "all_required_hit": all(v >= 0.6 for v in values),
            "policy_hit": (all if policy == "all" else any)(v >= 0.6 for v in values),
            "evidence_policy": policy,
            "definition": "实际模型输入内来源匹配的标注证据字符覆盖>=60%；仅为资料覆盖，不是答案正确率。"}

def retrieval_metrics(case, docs):
    policy = case.get("evidence_policy", "any")
    if policy not in ("any", "all"):
        raise ValueError("Unknown evidence_policy: " + str(policy))
    if not case.get("evidence"):
        return None
    coverage = {}
    required_coverage = {}
    basename = lambda value: str(value).replace("\\", "/").rsplit("/", 1)[-1]
    for k in (1, 3, 5):
        values = []
        for evidence in case["evidence"]:
            source = basename(evidence["source"])
            passages = [doc["text"] for doc in docs[:k] if basename(doc["metadata"].get("source", "")) == source]
            values.append(evidence_coverage(evidence["quote"], passages))
        coverage[k] = max(values)
        required_coverage[k] = values
    rank = next((k for k in range(1, len(docs)+1)
                 if max(evidence_coverage(e["quote"], [d["text"] for d in docs[:k]
                        if basename(d["metadata"].get("source", "")) == basename(e["source"])])
                        for e in case["evidence"]) >= 0.6), None)
    return {"evidence_coverage": {str(k):v for k,v in coverage.items()},
            "hit": {str(k):v >= 0.6 for k,v in coverage.items()},
            "required_evidence_coverage": {str(k): v for k, v in required_coverage.items()},
            "all_required_hit": {str(k): all(v >= 0.6 for v in values)
                                 for k, values in required_coverage.items()},
            "policy_hit": {str(k): (all(v >= 0.6 for v in required_coverage[k])
                                     if policy == "all" else coverage[k] >= 0.6) for k in coverage},
            "evidence_policy": policy,
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
