"""Model-facing metadata must preserve the frozen signatures without strict noise."""
import json
import re

import pytest

from service_desk.contracts import ARGUMENT_MODELS, SERVICE_TOOL_NAMES
from service_desk.tool_schema import model_tool_schemas


def test_all_twelve_openai_tools_are_present_in_frozen_order():
    schemas = model_tool_schemas()
    assert len(schemas) == 12
    assert tuple(item['function']['name'] for item in schemas) == SERVICE_TOOL_NAMES
    assert all(item['type'] == 'function' for item in schemas)


@pytest.mark.parametrize('name', SERVICE_TOOL_NAMES)
def test_signature_types_enums_and_required_fields_match_strict_contract(name):
    function = next(item['function'] for item in model_tool_schemas() if item['function']['name'] == name)
    model = ARGUMENT_MODELS[name]
    parameters = function['parameters']
    assert set(parameters['properties']) == set(model.model_fields)
    assert set(parameters['required']) == {field for field, info in model.model_fields.items() if info.is_required()}
    for field, actual in parameters['properties'].items():
        strict = model.model_json_schema()['properties'][field]
        non_null = next((item for item in strict.get('anyOf', []) if item.get('type') != 'null'), strict)
        assert actual['type'] == non_null['type']
        assert actual.get('enum') == non_null.get('enum')
        assert actual['description']
    assert 20 <= len(re.findall(r'[\u4e00-\u9fff]', function['description'])) <= 40


def test_only_lean_keywords_no_identity_or_nullable_parameters():
    schemas = model_tool_schemas()
    def visit(value):
        if isinstance(value, dict):
            assert not set(value) & {'pattern', 'anyOf', 'maxLength', 'minLength', 'title', 'default', 'user_id'}
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(schemas)
    assert 'null' not in json.dumps(schemas)
    for item in schemas:
        parameters = item['function']['parameters']
        assert set(parameters) == {'type', 'properties', 'required'}
        for prop in parameters['properties'].values():
            assert set(prop) <= {'type', 'enum', 'description'}


def test_returns_fresh_schema_without_mutating_strict_models():
    strict_before = {name: model.model_json_schema() for name, model in ARGUMENT_MODELS.items()}
    schemas = model_tool_schemas()
    schemas[1]['function']['parameters']['properties']['code']['type'] = 'integer'
    assert model_tool_schemas()[1]['function']['parameters']['properties']['code']['type'] == 'string'
    assert strict_before == {name: model.model_json_schema() for name, model in ARGUMENT_MODELS.items()}
