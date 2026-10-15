from copy import deepcopy

import pytest

from service_desk import plan_core, planner
from service_desk.render import guard_text
from test_service_reads import seed_path, read
from test_service_agent import db, graph
from test_service_plan_agent import visit_plan, planned


def test_compact_schema_semantics_and_named_description_property():
    original = plan_core.plan_json_schema()
    saved = deepcopy(original)
    def without_annotations(node, property_map=False):
        if isinstance(node, list):
            return [without_annotations(v) for v in node]
        if not isinstance(node, dict):
            return node
        return {k: without_annotations(v, k in ('properties', '$defs'))
                for k, v in node.items() if property_map or k not in ('title', 'description')}
    compact = planner.compact_schema(original)
    assert compact == without_annotations(original)
    assert original == saved
    custom = {'title': 'root', 'type': 'object', 'properties': {
        'description': {'type': 'string', 'description': 'annotation', 'minLength': 2}},
        'required': ['description'], 'additionalProperties': False}
    assert planner.compact_schema(custom) == {'type': 'object', 'properties': {
        'description': {'type': 'string', 'minLength': 2}}, 'required': ['description'], 'additionalProperties': False}
