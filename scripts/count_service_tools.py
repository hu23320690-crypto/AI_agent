"""Count actual ChatOllama.bind_tools payloads with the offline pinned tokenizer."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_ollama import ChatOllama
from model.token_count import MODEL_NAME, get_text_counter, load_cache_identity
from service_desk.tools import build_service_tools


def count_service_tools():
    identity = load_cache_identity()
    if identity is None:
        raise ValueError('validated offline Qwen tokenizer is unavailable')
    model = ChatOllama(model=MODEL_NAME, validate_model_on_init=False)
    bound = model.bind_tools(build_service_tools()).kwargs['tools']
    counter = get_text_counter(SimpleNamespace(model=MODEL_NAME),
                               expected_digest=identity['model_digest'])
    if counter is None:
        raise ValueError('offline Qwen counter is unavailable')

    def serialize(value):
        # Matches HTTPX encode_json compact Unicode serialization, after binding.
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

    serialized = serialize(bound)
    return {
        'binding': 'langchain_ollama.ChatOllama.bind_tools',
        'serialization': 'compact UTF-8 JSON, insertion order, no ASCII escaping',
        'method': counter.method, 'model_digest': counter.model_digest,
        'total_tokens': counter.count(serialized), 'utf8_bytes': len(serialized.encode('utf-8')),
        'per_tool': {tool['function']['name']: counter.count(serialize(tool)) for tool in bound},
        'includes_chat_template_framing': False,
    }


if __name__ == '__main__':
    print(json.dumps(count_service_tools(), ensure_ascii=False, indent=2))
