"""Read-only callbacks; observe real requests before history can be compressed."""
from copy import deepcopy
from threading import RLock
import time

from langchain_core.callbacks import BaseCallbackHandler
from evaluation.service_eval import parse_content


class TurnTrace(BaseCallbackHandler):
    def __init__(self, on_change=None):
        self.requests, self.calls, self.outputs = [], [], []
        self.lock = RLock()
        self.on_change = on_change or (lambda: None)

    def on_chat_model_start(self, serialized, messages, **kwargs):
        from rag.service_context import evaluation_rag_dispatch_active
        if evaluation_rag_dispatch_active():
            return  # Captured once by the capability-bound nested observer.
        self._observe_requests(messages, 'agent', kwargs.get('invocation_params', {}))

    def observe_rag_model(self, messages, *, parameters):
        self._observe_requests(messages, 'rag', parameters)

    def _observe_requests(self, messages, layer, parameters):
        with self.lock:
            for batch in messages:
                self.requests.append({'messages': [m.model_dump(mode='json') for m in batch],
                                      'model_layer': layer, 'parameters': deepcopy(parameters),
                                      'started_at': time.time()})
            self.on_change()

    def on_llm_end(self, response, **kwargs):
        from rag.service_context import evaluation_rag_dispatch_active
        if evaluation_rag_dispatch_active():
            return
        with self.lock:
            for group in response.generations:
                for generation in group:
                    message = getattr(generation, 'message', None)
                    if message is not None:
                        self.outputs.append(message.model_dump(mode='json'))
                        self.calls.extend(deepcopy(getattr(message, 'tool_calls', [])))
            self.on_change()

    def observe_tool(self, call, result=None, error=None, *, started_at):
        with self.lock:
            payload = parse_content(getattr(result, 'content', None))
            item = next((row for row in self.calls if row.get('id') == call['id']), None)
            if item is None:
                item = deepcopy(call)
                self.calls.append(item)
            item.update(status=getattr(result, 'status', 'error'), content=payload,
                        started_at=started_at, completed_at=time.time())
            if error is not None:
                item.update(status='error', error_type=type(error).__name__)
            if isinstance(payload, dict) and payload.get('status') in ('denied', 'failed'):
                item['status'] = 'error'
            self.on_change()

    def snapshot(self):
        with self.lock:
            return deepcopy({'model_requests': self.requests, 'tool_calls': self.calls,
                             'model_outputs': self.outputs})
