"""Quote a clearly matched, complete source answer to one yes/no question.

This conservative lexical path prevents free elaboration after a source has
already answered the question. It is not a general semantic matching system.
Ambiguity, weak overlap, multi-part requests and incomplete entries fall back
to generation. The caller owns authorization and source-boundary checks.
"""
from dataclasses import dataclass
import re

from rag.hybrid import tokenize


_BOOLEAN = re.compile(r'可以|能不能|能否|可不可以|是否|还会|可否')
_MULTIPLE = re.compile(r'另外|同时|还有|分别|以及|并且|多少钱|价格|费用|成本')
_FOLLOWUP = re.compile(r'怎么|如何|为什么|原因|步骤|顺序|哪些|多久|多长时间|时长|处理|校准')
_QUESTION = re.compile(r'^\s*\d{1,3}[.、)]\s*(?:\*\*)?(?P<question>[^\n]{2,120}?[？?])(?:\*\*)?\s*$')
_QUESTION_FILLER = re.compile(r'可不可以|可以|能不能|能否|是否|还会|可否|用在|[吗？?]')


@dataclass(frozen=True)
class SourceAnswer:
    question: str
    answer: str
    line: str
    document: object
    score: float


def extract_boolean_answer(query, docs, *, question=None, boundary_check=None):
    original = question or query
    if (not isinstance(original, str) or not _BOOLEAN.search(original)
            or _MULTIPLE.search(original) or len(re.findall(r'[？?]', original)) > 1
            or boundary_check is None):
        return None
    # A matched yes/no clause cannot replace a request for a procedure,
    # explanation, duration or follow-up actions in the same sentence.
    if _FOLLOWUP.search(original):
        return None
    terms = set(tokenize(query))
    candidates = []
    for document in docs:
        if not document.metadata.get('source_id') or document.metadata.get('source_version') is None:
            continue
        lines = document.page_content.splitlines()
        for index, line in enumerate(lines[:-1]):
            match = _QUESTION.fullmatch(line)
            if not match or not _BOOLEAN.search(match['question']):
                continue
            source_question = match['question']
            question_terms = set(tokenize(_QUESTION_FILLER.sub('', source_question)))
            common = terms.intersection(question_terms)
            score = len(common) / max(1, len(question_terms))
            if len(common) < 4 or score < .5:
                continue
            following = next((value.strip() for value in lines[index + 1:] if value.strip()), '')
            if not following.startswith('- '):
                continue
            body = following[2:].strip()
            if not body or not body.endswith(('。', '.', '！', '!')):
                continue
            candidates.append(SourceAnswer(source_question, body, following, document, score))
    if not candidates:
        return None
    highest = max(item.score for item in candidates)
    finalists = [item for item in candidates if item.score >= highest - .1]
    identities = {(item.question, item.answer) for item in finalists}
    if len(identities) != 1:
        return None
    chosen = finalists[0]
    if boundary_check(chosen.document, chosen.line) is not True:
        return None
    # Disagreeing answers to the same question are never silently selected.
    if any(item.question == chosen.question and item.answer != chosen.answer for item in candidates):
        return None
    return '资料对“' + chosen.question + '”的说明：\n\n' + chosen.answer
