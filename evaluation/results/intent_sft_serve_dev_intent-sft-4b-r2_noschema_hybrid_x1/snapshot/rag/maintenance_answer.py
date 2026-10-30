"""Conservative extraction of complete maintenance entries from validated docs.

This helper does not authorize documents or read source files. The caller must
validate retrieved documents before calling, retain their commit checks, and
revalidate before delivery. A source match establishes provenance, not truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import PurePosixPath
import re
from collections.abc import Callable, Sequence

from langchain_core.documents import Document


_MAINTENANCE = re.compile(r'维护|保养|多久|多长时间|周期|频率|清洗|冲洗|清理|擦拭|更换|晾干|检查|破损|损坏|磨损')
_ACTIONS = re.compile(r'清洗|冲洗|清理|擦拭|更换|晾干|检查|润滑|清洁|消毒|存放')
_OTHER_TASK = re.compile(r'价格|多少钱|购买|哪里买|型号推荐|产品推荐|总结全文|所有部件')
_CYCLE = re.compile(r'多久|多长时间|周期|频率|间隔|何时(?:更换|换)')
_PROCEDURE = re.compile(r'(?:怎么|如何)(?:拆|安装|维修|修复|清理|清洗)|步骤|顺序')
_DRY_DURATION = re.compile(r'晾干[^？?\n]{0,12}(?:多久|多长时间|小时)|(?:多久|多长时间)[^？?\n]{0,8}晾干')
_COMPARISON = re.compile(r'分别|各自|分开|章节|相比|比较|区别|不同(?:之处|周期)')
_REFERENCE = re.compile(r'它|该部件|这个部件|这一项|上述|刚才|原来|此前|之前')
_ENTRY = re.compile(r'^\s*(?:\d{1,3}[.、)]\s*)?(?P<label>[^:：\n]{1,45})[:：](?P<body>[^\n]+)\s*$')
_LABEL = re.compile(r'^[\u4e00-\u9fffA-Za-z0-9/ _\-（）()]+$')
_ITEM_BOUNDARY = re.compile(r'^\s*(?:\d{1,3}[.、)]\s*|#{1,6}\s+)')
_NEGATED_OBJECT = re.compile(r'(?:不是|不问|不要|不用|不需要|而非|而不是|排除)[^，,。；;？?]{0,12}$')
_SOURCE_VERB = r'按照|按|依据|根据|参考|采用|使用|选用|引用|遵循|用'
_SOURCE_ATTRIBUTION = re.compile(
    r'(?P<negative>(?:不要|不需要|无需|禁止|别|勿|不)(?:再|继续|直接|仍|仅|只|去|从|以)*'
    rf'(?:{_SOURCE_VERB})|排除|不用|不是|而非|而不是|不要|不需要|别|勿)'
    rf'|(?P<affirmative>分别(?:{_SOURCE_VERB})|而是|改为|改按|改用|只按|请按|{_SOURCE_VERB})')
_SOURCE_CLAUSE_BOUNDARY = re.compile(r'[，,。；;？?！!\n]')


def requested_source_ids(query: str, authorized: dict) -> set[str]:
    """Resolve an explicit source title against the current administrator ledger.

    A short title is accepted only in a source-attribution phrase and only when
    it uniquely prefixes a file title. Ordinary maintenance words are not a
    licence to read all sources, and a caller-provided path never selects a file.
    """
    titles = {key: PurePosixPath(value['path']).stem for key, value in authorized.items()}
    if not titles:
        return set()
    filenames = {key: PurePosixPath(value['path']).name for key, value in authorized.items()}
    title_pattern = re.compile('|'.join(re.escape(title) for title in sorted(set(titles.values()), key=len, reverse=True) if title))
    def affirmative_at(position):
        prefix = _SOURCE_CLAUSE_BOUNDARY.split(query[:position])[-1]
        # Source titles themselves may contain attribution words. Mask earlier
        # titles before reading the clause's instruction about the next source.
        prefix = title_pattern.sub(lambda match: ' ' * len(match[0]), prefix)
        markers = list(_SOURCE_ATTRIBUTION.finditer(prefix))
        return not markers or markers[-1].group('negative') is None
    events = []
    # The longest title consumes its span. A shorter catalogue title contained
    # in it is not an additional source request. Equal stems across extensions
    # stay ambiguous unless the user explicitly writes one complete filename.
    for mention in title_pattern.finditer(query):
        keys = {key for key, title in titles.items() if title == mention[0]}
        explicit = {key for key in keys if query.startswith(filenames[key], mention.start())}
        for key in explicit or keys:
            events.append((mention.start(), key, affirmative_at(mention.start())))
    mentions = re.finditer(r'(?:按|根据|依据|参考|依照|遵循)([\u4e00-\u9fffA-Za-z0-9_]{2,20}?)(?:资料|手册|说明)', query)
    for mention in mentions:
        matches = {key for key, title in titles.items() if title.startswith(mention[1])}
        if len(matches) == 1:
            events.append((mention.start(1), next(iter(matches)), affirmative_at(mention.start(1))))
    # A later explicit correction can restore an excluded source, or withdraw
    # a source requested earlier. Do not retain an earlier positive mention
    # after the user has explicitly excluded that same title.
    selected = {}
    for _, key, affirmative in sorted(events):
        selected[key] = affirmative
    return {key for key, affirmative in selected.items() if affirmative}


def scoped_entry_documents(query: str, sources: Sequence[Document], *, pipeline: str,
                           max_entries: int) -> list[Document]:
    """Select literal complete named entries from already authorized full sources.

    This is only for an explicit source request. No source file is opened here.
    It preserves physical offsets and section labels from those same bytes; the
    service must validate them and prove each boundary again before delivery.
    Unclear objects, versions, qualifiers or too many entries do not take this
    deterministic route.
    """
    complete_sources = [Document(page_content=source.page_content,
                                 metadata=dict(source.metadata, chunk_index=0, chunk_count=1))
                        for source in sources]
    entries = _entries(complete_sources)
    found = _matches(query, entries)
    if not found or len({entry.component for entry in found}) != 1:
        return []
    labels = {entry.label for entry in found}
    if len(labels) > 1:
        qualified = [entry for entry in found if entry.qualifier and
                     _compact(re.sub(r'(?:机型|款)$', '', entry.qualifier)) in _compact(query)]
        if len({entry.label for entry in qualified}) != 1:
            return []
        found = qualified
    component = found[0].component
    qualifier = re.sub(r'(?:机型|款)$', '', found[0].qualifier)
    # A bare family name cannot select one retrieved subtype. A suffix such
    # as a component's buckle is an attached part, whereas another name ending
    # in the full component label remains a potentially different subtype.
    if any(entry.component != component and entry.component.endswith(component) for entry in entries):
        if not qualifier or _compact(qualifier) not in _compact(query):
            return []
    if len({(entry.source_id, entry.source_version) for entry in found}) != 1:
        return []
    bodies = {(entry.label, entry.body) for entry in found}
    if len({entry.body for entry in found}) != 1:
        return []
    separate_sections = bool(re.search(r'章节|分别|分开|不同', query))
    selected = []
    for source in sources:
        section, offset = '', 0
        for line in source.page_content.splitlines(keepends=True):
            literal = line.rstrip('\r\n')
            if literal.lstrip().startswith('#'):
                section = literal.lstrip('# ').strip()
            match = _ENTRY.fullmatch(literal)
            named = bool(match and (match['label'].strip(), match['body'].strip()) in bodies)
            # Additional prose entries need the same explicit subtype context,
            # not merely a contained generic name such as another object's brush.
            narrative = bool(separate_sections and qualifier and qualifier in literal
                             and component in literal and _ACTIONS.search(literal)
                             and not match and re.match(r'^\s*\d{1,3}[.、)]', literal)
                             and literal.endswith(('。', '.', '！', '!')))
            if narrative and any(entry.component != component for entry in _matches(literal, entries)):
                narrative = False
            if named or narrative:
                metadata = dict(source.metadata, pipeline=pipeline, start_index=offset,
                                chunk_index=0, chunk_count=1, source_section=section,
                                chunk_sha256=hashlib.sha256(literal.encode('utf-8')).hexdigest())
                identity = f"{metadata['source_id']}:{metadata['source_version']}:{metadata.get('source_sha256')}:{pipeline}:{offset}:{literal}"
                metadata['chunk_id'] = 'source-entry-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
                selected.append(Document(page_content=literal, metadata=metadata))
            offset += len(line)
    # A request for one explicit section must not silently mix other sections.
    section_names = {doc.metadata['source_section'] for doc in selected}
    specific = {section for section in section_names if section and
                re.split(r'维护|与|[（(]', section, maxsplit=1)[0] in query}
    if specific and not separate_sections:
        selected = [doc for doc in selected if doc.metadata['source_section'] in specific]
    unique = {(doc.metadata['source_id'], doc.metadata['start_index']): doc for doc in selected}
    return list(unique.values()) if 0 < len(unique) <= max_entries else []


def quote_scoped_entries(query: str, docs: Sequence[Document], *, question: str | None = None,
                         boundary_check=None) -> str | None:
    """Deliver complete source-selected entries without generating extra facts."""
    original = question or query
    if (not docs or boundary_check is None or not _MAINTENANCE.search(original)
            or _OTHER_TASK.search(original) or _DRY_DURATION.search(original)
            or re.search(r'预测|估算|剩余|剩下|还能', original)
            or not re.search(r'周期|频率|多久|多长时间|更换|清理|清洗|冲洗', original)):
        return None
    for document in docs:
        if boundary_check(document, document.page_content) is not True:
            return None
    rows = []
    for document in docs:
        section = document.metadata.get('source_section')
        rows.append(('【' + section + '】\n' if section else '') + document.page_content)
    return '所指定资料的完整条目（各章节分别保留原条件）：\n\n' + '\n\n'.join(rows)


@dataclass(frozen=True)
class MaintenanceEntry:
    component: str
    qualifier: str
    label: str
    body: str
    source_id: str
    source_version: str


def _compact(value: str) -> str:
    return re.sub(r'\s+', '', value).casefold()


def _entries(docs: Sequence[Document], boundary_check=None) -> list[MaintenanceEntry]:
    result = []
    for doc in docs:
        if not isinstance(doc, Document) or not isinstance(doc.page_content, str):
            continue
        source_id, version = doc.metadata.get('source_id'), doc.metadata.get('source_version')
        # Absent provenance is not repaired with a made-up citation or identity.
        if not isinstance(source_id, str) or not source_id or version is None:
            continue
        lines = doc.page_content.splitlines()
        chunk_index, chunk_count = doc.metadata.get('chunk_index'), doc.metadata.get('chunk_count')
        source_end = (type(chunk_index) is int and type(chunk_count) is int and
                      chunk_count > 0 and chunk_index == chunk_count - 1)
        for index, line in enumerate(lines):
            match = _ENTRY.fullmatch(line)
            if match is None:
                continue
            label, body = match['label'].strip(), match['body'].strip()
            if (not _LABEL.fullmatch(label) or not _ACTIONS.search(body)
                    or not body.endswith(('。', '.', '！', '!'))):
                continue
            following = [value for value in lines[index + 1:] if value.strip()]
            proven_boundary = bool(_ITEM_BOUNDARY.match(following[0])) if following else source_end
            accepted_boundary = (boundary_check(doc, line) is True if boundary_check is not None
                                 else proven_boundary)
            if not accepted_boundary:
                # A full stop alone is not proof of a complete item: another
                # sentence may have been cut into the next chunk. Require a
                # following item/header, validated end-of-source metadata, or
                # a trusted source-boundary check from the application.
                continue
            component = re.sub(r'[（(][^）)]*[）)]', '', label).strip()
            qualifiers = re.findall(r'[（(]([^）)]*)[）)]', label)
            if (not component or '(' in component or '（' in component
                    or ')' in component or '）' in component):
                continue
            result.append(MaintenanceEntry(component, ' '.join(qualifiers), label,
                                           body, source_id, str(version)))
    return result


def _matches(text: str, entries: Sequence[MaintenanceEntry]) -> list[MaintenanceEntry]:
    compact = _compact(text)
    found = []
    for entry in entries:
        occurrences = re.finditer(re.escape(_compact(entry.component)), compact)
        if any(not _NEGATED_OBJECT.search(compact[max(0, match.start() - 40):match.start()])
               for match in occurrences):
            found.append(entry)
    # Do not let a contained generic name override a clearly named longer object.
    return [entry for entry in found if not any(
        entry.component != other.component and
        _compact(entry.component) in _compact(other.component)
        for other in found)]


def extract_maintenance_answer(query: str, docs: Sequence[Document], *,
                               question: str | None = None,
                               boundary_check: Callable[[Document, str], bool] | None = None) -> str | None:
    """Quote one unambiguous complete entry, otherwise return None for the LLM.

    Names/actions/periods come exclusively from the supplied evidence. Explicit
    names in the original question supersede a retrieval query expanded with
    prior user context. Pronoun-only questions may use that expanded query;
    this helper never recovers a target from prior assistant claims.
    """
    original = question or query
    if (not isinstance(query, str) or not isinstance(original, str)
            or not _MAINTENANCE.search(original) or not _CYCLE.search(original)
            or _OTHER_TASK.search(original) or _PROCEDURE.search(original)
            or _DRY_DURATION.search(original) or _COMPARISON.search(original)):
        return None
    entries = _entries(docs, boundary_check)
    original_matches = _matches(original, entries)
    if original_matches:
        found = original_matches
        selector = original
    elif question is not None and question != query:
        if not _REFERENCE.search(original):
            return None
        found, selector = _matches(query, entries), query
    else:
        found, selector = _matches(query, entries), query
    if not found or len({entry.component for entry in found}) != 1:
        return None
    component = found[0].component
    # A generic source entry plus more specific sibling objects is ambiguous.
    # In particular, a bare family term cannot stand in for a named subtype.
    if any(component != entry.component and _compact(component) in _compact(entry.component)
           for entry in entries):
        return None
    labels = {entry.label for entry in found}
    if len(labels) > 1:
        qualified = [entry for entry in found if entry.qualifier and
                     _compact(entry.qualifier) in _compact(selector)]
        if len({entry.label for entry in qualified}) != 1:
            return None
        found = qualified
    # Overlapping duplicate chunks are harmless; a disagreeing complete clause
    # or two versions of one source must be handled explicitly, not merged.
    if len({_compact(entry.body) for entry in found}) != 1:
        return None
    versions = {}
    for entry in found:
        versions.setdefault(entry.source_id, set()).add(entry.source_version)
    if any(len(value) > 1 for value in versions.values()):
        return None
    chosen = found[0]
    # A replacement entry cannot stand in for a separately requested cleaning
    # procedure. If an action is absent, let generation combine other evidence.
    if re.search(r'清洗|清理|清洁|冲洗|擦拭', original) and not re.search(r'清洗|清理|清洁|冲洗|擦拭', chosen.body):
        return None
    if re.search(r'更换|再换|换新', original) and '更换' not in chosen.body:
        return None
    for action in ('润滑', '存放', '消毒', '检查'):
        if action in original and action not in chosen.body:
            return None
    return '维护资料中的完整条目（保留原文条件）：\n\n' + chosen.label + '：' + chosen.body
