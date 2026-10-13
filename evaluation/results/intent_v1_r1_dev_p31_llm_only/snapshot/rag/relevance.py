"""Preserve RRF ordering while reserving the final source slot for a new aspect.

A per-source quota can discard an answer-bearing passage when earlier passages
all repeat the same part of the question. Keep that source's first cap-1 fused
passages, then promote the passage covering the most still-uncovered query
terms into its final slot. Candidate eligibility remains the caller's job.
This is a lexical diversity heuristic, not a safety or answerability classifier.
"""
from collections import Counter, defaultdict
import math

from rag.hybrid import tokenize


class QueryCoverageReranker:
    def __init__(self, documents):
        documents = list(documents)
        self.size = len(documents)
        self.frequency = Counter(
            term for document in documents for term in set(tokenize(document.page_content)))

    def scores(self, query, candidates, *, excluded_terms=frozenset()):
        terms = sorted((set(tokenize(query)) & self.frequency.keys()) - excluded_terms)
        if not terms:
            return [0.] * len(candidates)
        weights = {term: math.log(1 + (self.size + .5) / (self.frequency[term] + .5))
                   for term in terms}
        denominator = sum(weights.values())
        document_terms = [set(tokenize(doc.page_content)) for doc in candidates]
        return [sum(weights[term] for term in terms if term in matched) / denominator
                for matched in document_terms]

    def rerank(self, query, candidates, *, source_cap=3):
        candidates = list(candidates)
        if source_cap < 1:
            raise ValueError("source_cap must be positive")
        groups = defaultdict(list)
        for rank, document in enumerate(candidates):
            # Missing provenance is never eligible in the production caller;
            # avoid grouping such documents into an artificial common source.
            source = document.metadata.get("source_id", ("unknown", rank))
            groups[source].append((rank, document))
        replacements = {}
        for group in groups.values():
            if len(group) <= source_cap:
                continue
            boundary = source_cap - 1
            covered = set(term for _, document in group[:boundary]
                          for term in tokenize(document.page_content))
            remaining = group[boundary:]
            scores = self.scores(query, [doc for _, doc in remaining], excluded_terms=covered)
            best = max(range(len(remaining)), key=lambda rank: (scores[rank], -rank))
            if best == 0:
                continue
            reordered = group[:boundary] + [remaining[best]] + [entry for rank, entry in enumerate(remaining) if rank != best]
            for (rank, _), (_, document) in zip(group, reordered):
                replacements[rank] = document
        return [replacements.get(rank, document) for rank, document in enumerate(candidates)]
