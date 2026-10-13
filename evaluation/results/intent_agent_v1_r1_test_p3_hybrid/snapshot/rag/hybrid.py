"""Small-corpus BM25 + reciprocal-rank fusion; no extra model dependency."""
import math
import re
from collections import Counter, defaultdict


def tokenize(text):
    tokens = []
    for span in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+(?:[.-][a-z0-9]+)*', text.lower()):
        if '\u4e00' <= span[0] <= '\u9fff':
            # Character bigrams retain Chinese part names without a dictionary.
            tokens.extend(span[i:i+2] for i in range(max(1, len(span)-1)))
        else:
            tokens.append(span)
    return tokens


def document_key(doc):
    return (doc.metadata.get('source', ''), doc.metadata.get('page', -1),
            doc.metadata.get('start_index', -1), doc.page_content)


class BM25Index:
    def __init__(self, documents, k1=1.2, b=.75):
        self.documents = list(documents)
        self.k1, self.b = k1, b
        self.terms = [Counter(tokenize(d.page_content)) for d in self.documents]
        self.lengths = [sum(t.values()) for t in self.terms]
        self.average = sum(self.lengths) / max(1, len(self.lengths)) or 1
        self.frequency = Counter(term for terms in self.terms for term in terms)

    def search(self, query, k):
        if k <= 0:
            return []
        scores = []
        query_terms = set(tokenize(query))
        for index, terms in enumerate(self.terms):
            score = 0.0
            for term in query_terms:
                tf = terms.get(term, 0)
                if not tf:
                    continue
                df = self.frequency[term]
                idf = math.log(1 + (len(self.documents)-df+.5)/(df+.5))
                score += idf * tf * (self.k1+1) / (tf+self.k1*(1-self.b+self.b*self.lengths[index]/self.average))
            if score > 0:
                scores.append((score, index))
        scores.sort(key=lambda item: (-item[0], document_key(self.documents[item[1]])))
        return [self.documents[index] for _, index in scores[:k]]


def fuse(rankings, k, rank_constant=60):
    if k <= 0:
        return []
    scores, documents = defaultdict(float), {}
    for ranking in rankings:
        seen = set()
        for rank, doc in enumerate(ranking, 1):
            key = document_key(doc)
            if key in seen:
                continue
            seen.add(key)
            documents[key] = doc
            scores[key] += 1 / (rank_constant+rank)
    keys = sorted(scores, key=lambda key: (-scores[key], key))[:k]
    return [documents[key] for key in keys]
