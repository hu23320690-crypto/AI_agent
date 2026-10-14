"""Explicit offline scripts for runner tests and smoke runs; never infer gold."""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch


def scripted_model(spec):
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from pydantic import Field

    class ScriptedModel(BaseChatModel):
        script: list = Field(default_factory=list)

        @property
        def _llm_type(self):
            return 'service-eval-scripted'

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, **kwargs):
            import time
            if not self.script:
                raise RuntimeError('Script exhausted')
            response = self.script.pop(0)
            if 'sleep' in response:
                time.sleep(response['sleep'])
            if 'error' in response:
                raise RuntimeError(response['error'])
            calls = response.get('calls', [])
            message = AIMessage(content=response.get('answer', ''), tool_calls=[
                {'name': row['name'], 'args': row.get('args', {}), 'id': f'script-{len(self.script)}-{i}'}
                for i, row in enumerate(calls)],
                response_metadata={'done_reason': 'length' if response.get('truncated') else 'stop'})
            return ChatResult(generations=[ChatGeneration(message=message)])

    return ScriptedModel(script=spec['responses'])


@contextmanager
def offline_dependencies(spec):
    """Every actual Ollama generation/embedding attempt is a test failure."""
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    with ExitStack() as stack:
        stack.enter_context(patch.object(ChatOllama, '_generate', side_effect=AssertionError('Real model forbidden')))
        stack.enter_context(patch.object(OllamaEmbeddings, 'embed_documents', side_effect=AssertionError('Real embedding forbidden')))
        stack.enter_context(patch('model.token_count.verify_local_cache', return_value=False))
        if 'rag_responses' in spec:
            from agent.context_budget import ContextPolicy
            stack.enter_context(patch('rag.rag_service.rag_chat_model',
                                     return_value=scripted_model({'responses': spec['rag_responses']})))
            stack.enter_context(patch('rag.rag_service.load_context_policy', return_value=ContextPolicy(
                window_tokens=32768, reserve_output_tokens=1024, reasoning_enabled=False)))
            yield
            return
        from agent.tools import agent_tools
        from types import SimpleNamespace
        stack.enter_context(patch.object(agent_tools, 'get_rag_service', return_value=SimpleNamespace(
            rag_summarize=lambda *a, **k: spec.get('rag_answer', '合成检索证据。'))))
        yield
