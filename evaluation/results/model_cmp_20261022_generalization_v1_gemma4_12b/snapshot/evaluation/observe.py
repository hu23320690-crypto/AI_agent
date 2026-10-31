"""Read-only observation at the actual Ollama generation boundary.

Formatting a candidate context is not evidence that it reached the model. Only
contexts found verbatim in an actual generation request are counted below.
"""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from threading import RLock
import time
from unittest.mock import patch


def json_value(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def seed_messages(spec):
    """Build completed synthetic pairs; never call a model to create the seed."""
    from langchain_core.messages import AIMessage, HumanMessage
    expected = {"generator", "pairs", "goal", "constraints", "user_template",
                "assistant_template", "acknowledged"}
    if not isinstance(spec, dict) or set(spec) != expected:
        raise ValueError("Invalid seed_history fields")
    if spec["generator"] != "synthetic_completed_pairs_v1":
        raise ValueError("Unknown seed_history generator")
    if type(spec["pairs"]) is not int or not 1 <= spec["pairs"] <= 128:
        raise ValueError("seed_history pairs must be an integer in 1..128")
    for name in ("goal", "user_template", "assistant_template", "acknowledged"):
        if not isinstance(spec[name], str) or not spec[name].strip():
            raise ValueError("Invalid seed_history " + name)
    if (not isinstance(spec["constraints"], list) or
            any(not isinstance(v, str) or not v.strip() for v in spec["constraints"])):
        raise ValueError("Invalid seed_history constraints")
    first = "\n".join([spec["goal"], *spec["constraints"]])
    messages = [HumanMessage(content=first), AIMessage(content=spec["acknowledged"])]
    for turn in range(2, spec["pairs"] + 1):
        messages.extend([HumanMessage(content=spec["user_template"].format(turn=turn)),
                         AIMessage(content=spec["assistant_template"].format(turn=turn))])
    return messages


class ModelObserver:
    def __init__(self, on_change=None):
        self.calls = []
        self.rag_answers = []
        self.runtime_snapshots = []
        self._contexts = {}
        self._lock = RLock()
        self._on_change = on_change or (lambda: None)

    def register_context(self, formatted, docs):
        if isinstance(formatted, str) and formatted:
            documents = [{"text": d.page_content, "metadata": json_value(d.metadata)} for d in docs]
            with self._lock:
                self._contexts[formatted] = documents

    def actual_contexts(self, messages):
        contents = [m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
                    for m in messages]
        with self._lock:
            return [{"formatted_context": text, "docs": deepcopy(docs)}
                    for text, docs in self._contexts.items()
                    if any(isinstance(content, str) and text in content for content in contents)]

    def record_generate(self, original, model, messages, *args, **kwargs):
        row = {"call_index": len(self.calls), "status": "running",
               "model": getattr(model, "model", None),
               "parameters": {name: json_value(getattr(model, name, None)) for name in
                              ("temperature", "num_ctx", "num_predict", "reasoning", "seed",
                               "top_k", "top_p", "repeat_penalty", "base_url", "format")},
               "messages": json_value(messages),
               "request_tools": json_value(kwargs.get("tools", [])),
               "request_format": json_value(kwargs.get("format")),
               "rag_contexts": self.actual_contexts(messages)}
        with self._lock:
            row["call_index"] = len(self.calls)
            self.calls.append(row)
            self._on_change()
        started = time.perf_counter()
        try:
            result = original(model, messages, *args, **kwargs)
            row["generations"] = [{"message": json_value(g.message),
                                   "generation_info": json_value(g.generation_info)}
                                  for g in result.generations]
            row["status"] = "ok"
            row["incomplete"] = any(
                g["message"].get("response_metadata", {}).get("done_reason") == "length"
                or (g["generation_info"] or {}).get("done_reason") == "length"
                for g in row["generations"])
            return result
        except BaseException as exc:
            row.update(status="error", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            row["seconds"] = time.perf_counter() - started
            with self._lock:
                self._on_change()

    def record_rag_answer(self, original, service, query, docs, *args, **kwargs):
        """Record actual service evidence for extractive/policy paths as well.

        These are service input documents, not proof of LLM input admission.
        actual_contexts and input_evidence continue to count only real model
        requests; budget trimming may remove some of these documents.
        """
        docs = list(docs)
        start = len(self.calls)
        row = {'query': query, 'question': kwargs.get('question'), 'status': 'running',
               'docs': [{'text': doc.page_content, 'metadata': json_value(doc.metadata)} for doc in docs],
               'definition': 'Observed production answer_documents inputs; separate from actual LLM inputs.'}
        with self._lock:
            self.rag_answers.append(row)
            self._on_change()
        try:
            answer = original(service, query, docs, *args, **kwargs)
            row.update(status='ok', answer=answer)
            return answer
        except BaseException as exc:
            row.update(status='error', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            row['model_request_indices'] = list(range(start, len(self.calls)))
            with self._lock:
                self._on_change()

    @contextmanager
    def installed(self):
        from langchain_ollama import ChatOllama
        from rag.rag_service import RagSummarizeService
        original_generate = ChatOllama._generate
        original_format = RagSummarizeService.format_context
        def generated(model, messages, *args, **kwargs):
            return self.record_generate(original_generate, model, messages, *args, **kwargs)
        def formatted(docs):
            docs = list(docs)
            text = original_format(docs)
            self.register_context(text, docs)
            return text
        with ExitStack() as stack:
            stack.enter_context(patch.object(ChatOllama, "_generate", generated))
            stack.enter_context(patch.object(RagSummarizeService, "format_context", staticmethod(formatted)))
            if hasattr(RagSummarizeService, 'answer_documents'):
                original_answer = RagSummarizeService.answer_documents
                def answered(service, query, docs, *args, **kwargs):
                    return self.record_rag_answer(original_answer, service, query, docs, *args, **kwargs)
                stack.enter_context(patch.object(RagSummarizeService, 'answer_documents', answered))
            # Historical business snapshots predate Runtime. Observe it only
            # when that version has it, without adding a runtime to old code.
            try:
                from agent.runtime import RunContext
            except ModuleNotFoundError:
                RunContext = None
            if RunContext is not None:
                for method_name in ("complete", "fail"):
                    original = getattr(RunContext, method_name)
                    def observed(run, *args, _original=original, **kwargs):
                        try:
                            return _original(run, *args, **kwargs)
                        finally:
                            with self._lock:
                                self.runtime_snapshots.append(json_value(run.snapshot()))
                                self._on_change()
                    stack.enter_context(patch.object(RunContext, method_name, observed))
            yield self


def input_evidence(case, calls):
    from evaluation.metrics import context_metrics
    contexts = [context for call in calls for context in call.get("rag_contexts", [])]
    docs = [doc for context in contexts for doc in context["docs"]]
    return {"observed_context_calls": sum(bool(c.get("rag_contexts")) for c in calls),
            "reference_occurrences": len(docs),
            "metrics": context_metrics(case, docs)}
