"""Dedicated intent model selection and the verified SFT data generator."""
import json
from datetime import date

import pytest

from agent.intent import llm_parser
from agent.intent.llm_parser import IntentConfig, build_messages, load_intent_config


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ('AGENT_INTENT_MODE', 'AGENT_INTENT_MODEL', 'AGENT_INTENT_PROMPT'):
        monkeypatch.delenv(name, raising=False)


def test_defaults_keep_shared_model_and_original_prompt():
    cfg = IntentConfig()
    assert cfg.model_name is None
    assert cfg.prompt == 'prompts/intent_parser.txt'


@pytest.mark.parametrize('prompt', ['../intent_parser.txt', 'prompts/../config/rag.yml',
                                    'prompts/sub/x.txt', 'prompts/x.md', '', None])
def test_prompt_must_be_a_txt_file_directly_under_prompts(prompt):
    with pytest.raises(ValueError):
        IntentConfig(prompt=prompt)


@pytest.mark.parametrize('name', ['', '   ', 3])
def test_model_name_must_be_null_or_nonempty_text(name):
    with pytest.raises(ValueError):
        IntentConfig(model_name=name)


def test_environment_overrides_model_and_prompt(monkeypatch, tmp_path):
    path = tmp_path / 'fictional-intent.yml'
    path.write_text('mode: rule\n', encoding='utf-8')
    monkeypatch.setenv('AGENT_INTENT_MODEL', 'fictional-sft:latest')
    monkeypatch.setenv('AGENT_INTENT_PROMPT', 'prompts/intent_parser_sft.txt')
    cfg = load_intent_config(path)
    assert (cfg.model_name, cfg.prompt) == ('fictional-sft:latest', 'prompts/intent_parser_sft.txt')


def test_build_messages_reads_the_selected_prompt_and_keeps_input_shape():
    messages = build_messages('2032年11月只列星辉率', history_queries=('上一轮',), previous_intent=None,
                              known_fields=('星辉率', '晶片寿命'), today=date(2033, 2, 14),
                              fallback_month='2032-11', prompt='prompts/intent_parser_sft.txt')
    assert messages[0].content == (llm_parser._ROOT / 'prompts/intent_parser_sft.txt').read_text(
        encoding='utf-8')
    assert json.loads(messages[1].content) == {
        'field_catalog': '星辉率\n晶片寿命', 'today': '2033-02-14', 'current_lookup_month': '2032-11',
        'previous_intent': None, 'history_queries': ['上一轮'], 'query': '2032年11月只列星辉率'}


def test_dedicated_model_copies_shared_settings_without_pinned_tokenizer():
    from model.factory import chat_model
    model = llm_parser.intent_model('fictional-sft:latest')
    assert model.model == 'fictional-sft:latest'
    assert model.metadata == {}
    assert model.temperature == 0 and model.format is not None
    # Ollama rewrites the prompt when think=false is sent; a dedicated model omits it.
    assert model.reasoning is None
    assert chat_model.model != 'fictional-sft:latest'


def test_shared_model_keeps_reasoning_off_and_schema_by_default():
    model = llm_parser.intent_model()
    assert model.reasoning is False and model.format is not None


def test_schema_constraint_can_be_disabled_for_a_dedicated_model():
    model = llm_parser.intent_model('fictional-sft:latest', schema_constrained=False)
    assert model.format is None and model.reasoning is None


@pytest.mark.parametrize('raw, expected', [('0', False), ('false', False), ('1', True), ('TRUE', True)])
def test_schema_environment_flag(monkeypatch, tmp_path, raw, expected):
    path = tmp_path / 'fictional-intent.yml'
    path.write_text('mode: rule\n', encoding='utf-8')
    monkeypatch.setenv('AGENT_INTENT_SCHEMA', raw)
    assert load_intent_config(path).schema_constrained is expected


def test_schema_environment_flag_rejects_other_values(monkeypatch, tmp_path):
    path = tmp_path / 'fictional-intent.yml'
    path.write_text('mode: rule\n', encoding='utf-8')
    monkeypatch.setenv('AGENT_INTENT_SCHEMA', 'off')
    with pytest.raises(ValueError):
        load_intent_config(path)


def test_parse_turn_intent_passes_dedicated_model_and_schema_choice(monkeypatch):
    from dataclasses import replace
    from langchain_core.messages import AIMessage
    from agent.runtime import RunContext
    seen = {}

    class Scripted:
        def invoke(self, messages):
            seen['system'] = messages[0].content
            return AIMessage(content=json.dumps({
                'task_type': 'report', 'fields': [], 'scope': 'unspecified', 'target_month': None,
                'target_mention': '', 'target_anchor': 'none', 'compare': False, 'baseline_month': None,
                'baseline_mention': '', 'excluded_fields': [], 'knowledge_question': '', 'unresolved': False}))

    def fake_model(name=None, schema_constrained=True):
        seen.update(name=name, schema=schema_constrained)
        return Scripted()

    monkeypatch.setattr(llm_parser, 'intent_model', fake_model)
    monkeypatch.setattr(llm_parser, 'enforce_request', lambda *args, **kwargs: None)
    cfg = replace(IntentConfig(mode='hybrid'), model_name='fictional-sft:latest',
                  prompt='prompts/intent_parser_sft.txt', schema_constrained=False)
    llm_parser.parse_turn_intent('2032年11月只列星辉率', history_queries=(), previous_intent=None,
                                 known_fields=('星辉率',), today=date(2033, 2, 14),
                                 fallback_month='2032-11', run=RunContext(), cfg=cfg)
    assert (seen['name'], seen['schema']) == ('fictional-sft:latest', False)
    assert seen['system'].startswith('Extract the report intent')


def test_generator_keeps_only_resolver_verified_rows_and_is_deterministic():
    from training.intent_sft.generate import generate
    first, _, _ = generate(60, 11)
    second, _, _ = generate(60, 11)
    assert first == second and len(first) == 60
    for row in first:
        request = json.loads(row['messages'][0]['content'])
        assert set(request) == {'field_catalog', 'today', 'current_lookup_month',
                                'previous_intent', 'history_queries', 'query'}
        label = json.loads(row['messages'][1]['content'])
        for item in label['fields']:
            assert any(item['mention'] in text for text in (request['query'], *request['history_queries']))
        if label['knowledge_question']:
            assert label['knowledge_question'] in request['query']


def test_generator_verification_rejects_a_label_that_contradicts_the_text():
    import random
    from training.intent_sft import generate as g
    rng = random.Random(5)
    world = g.World(rng)
    draft = None
    while draft is None or draft.fictional:
        draft = g.b_field_rephrase(rng, world)
    assert g.verify(draft)[1] is None
    draft.target = g.shift(draft.target, 1)
    assert g.verify(draft)[1] == 'hybrid:conflict:month_unsupported'
