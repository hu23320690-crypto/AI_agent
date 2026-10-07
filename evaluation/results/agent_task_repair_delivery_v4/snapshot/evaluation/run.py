"""Frozen baseline runner. Sequential local inference; resumable per-case records."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import tempfile
import urllib.request
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation/cases.jsonl"

def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def dump(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name+".", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
        json.dump(value, file, ensure_ascii=False, indent=2)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def portable_relative_path(name):
    """Read legacy Windows manifest paths on either platform, retaining hashes."""
    return Path(name.replace('\\', '/'))

def business_files():
    paths = [ROOT/"app.py"]
    for folder in ("agent","rag","utils","model","prompts","config"):
        paths.extend(p for p in (ROOT/folder).rglob("*") if p.suffix in (".py",".txt",".yml",".json") and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(paths)}

def evaluation_files():
    # Analysis/reporting can run after inference. These three files alone
    # implement executed requests, observation, and evidence measurements.
    return {"evaluation/"+name: digest(ROOT/"evaluation"/name)
            for name in ("run.py", "observe.py", "metrics.py")}

def environment_identity(dataset, timeout):
    """Resolve mutable model tags on every resume, not just the first run."""
    import yaml
    config = yaml.safe_load((ROOT/"config/rag.yml").read_text(encoding="utf-8"))
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    with urllib.request.urlopen(host+"/api/tags", timeout=10) as response:
        available = json.load(response)["models"]
    selected = {}
    for role, key in (("chat", "chat_model_name"), ("embedding", "embedding_model_name")):
        name = config[key]
        matches = [m for m in available if m["name"] == name or m["name"] == name+":latest"]
        if len(matches) != 1:
            raise RuntimeError("Configured model tag unavailable or ambiguous: " + name)
        selected[role] = {"configured_name": name, "name": matches[0]["name"], "digest": matches[0]["digest"]}
    variant = ROOT/"variant_identity.json"
    sources = json.loads((dataset.parent/"dataset_manifest.json").read_text(encoding="utf-8"))["files"]
    actual_sources = {name: digest(ROOT/portable_relative_path(name)) for name in sources}
    if actual_sources != sources:
        raise RuntimeError("Frozen source bytes changed")
    date_inputs = {"execution_month": date.today().strftime("%Y-%m")} if "$CURRENT_MONTH" in dataset.read_text(encoding="utf-8-sig") else {}
    return {"identity_version": 2, "code_sha256": business_files(),
            **date_inputs,
            "evaluation_sha256": evaluation_files(), "dataset_sha256": digest(dataset),
            "dataset_manifest_sha256": digest(dataset.parent/"dataset_manifest.json"),
            "source_sha256": actual_sources,
            "model_identity": selected, "ollama_host": host,
            "model_configuration": config,
            "temperature": 0, "sampling_note": "Production factory source is hashed; each actual model request records its parameters.",
            "dependencies": {name: importlib.metadata.version(name) for name in
                             ("langchain", "langchain-core", "langchain-ollama", "langgraph", "chromadb")},
            "python": sys.version, "platform": platform.platform(),
            "timeout_seconds": timeout, "inference_concurrency": 1,
            "variant_identity": json.loads(variant.read_text(encoding="utf-8")) if variant.exists() else None,
            "variant_identity_sha256": digest(variant) if variant.exists() else None}

def assert_resume_identity(previous, current):
    changed = [key for key, value in current.items() if previous.get(key) != value]
    if changed:
        raise RuntimeError("Cannot resume changed evaluation inputs ("+", ".join(changed)+
                           "); choose a new --run directory.")

def verify_dataset(dataset=DATASET):
    dataset = Path(dataset)
    cases = read_rows(dataset)
    manifest = json.loads((dataset.parent/"dataset_manifest.json").read_text(encoding="utf-8"))
    assert digest(dataset) == manifest["dataset_sha256"], "Dataset changed; version and manifest must be updated"
    assert len({c["id"] for c in cases}) == len(cases) == manifest['case_count']
    for name, expected in manifest["files"].items():
        assert digest(ROOT/portable_relative_path(name)) == expected, f"Source changed: {name}"
    for case in cases:
        if case.get("evidence_policy", "any") not in ("any", "all"):
            raise ValueError("Invalid evidence_policy: " + case["id"])
        if case.get("seed_history"):
            from evaluation.observe import seed_messages
            seed_messages(case["seed_history"])
        for evidence in case.get("evidence", []):
            lines = (ROOT/portable_relative_path(evidence["source"])).read_text(encoding="utf-8-sig").splitlines()
            selected = "\n".join(lines[evidence["line_start"]-1:evidence["line_end"]])
            assert evidence["quote"] in selected, f"Wrong source anchor: {case['id']}"
        for turn in case.get("turns", []):
            if turn.get("evidence_policy", "any") not in ("any", "all"):
                raise ValueError("Invalid turn evidence_policy: " + case["id"])
            for evidence in turn.get("evidence", []):
                lines = (ROOT/portable_relative_path(evidence["source"])).read_text(encoding="utf-8-sig").splitlines()
                selected = "\n".join(lines[evidence["line_start"]-1:evidence["line_end"]])
                assert evidence["quote"] in selected, f"Wrong turn source anchor: {case['id']}"
    return cases

def telemetry():
    from langchain_core.callbacks import BaseCallbackHandler
    class Recorder(BaseCallbackHandler):
        def __init__(self):
            self.models, self.calls, self.results = [], [], []
        def on_llm_end(self, response, **kwargs):
            for generations in response.generations:
                for generation in generations:
                    message = getattr(generation, "message", None)
                    if message is not None:
                        self.models.append({"usage": getattr(message, "usage_metadata", None),
                                            "metadata": getattr(message, "response_metadata", {})})
                        self.calls.extend(message.tool_calls if hasattr(message, "tool_calls") else [])
        def on_tool_end(self, output, **kwargs):
            self.results.append({"name":getattr(output,"name",None),
                "status":getattr(output,"status",None), "content":getattr(output,"content",str(output))})
    return Recorder()

def worker(mode, case, run, case_index=None):
    from evaluation.metrics import tool_selection
    from evaluation.observe import ModelObserver, json_value, seed_messages, input_evidence
    from unittest.mock import patch
    from contextlib import nullcontext
    recorder = telemetry()
    start = time.perf_counter()
    row = {"id":case["id"], "mode":mode, "status":"running", "turns":[],
           "semantic_review": None, "seeded_turns": 0, "model_calls": recorder.models,
           "tool_calls": recorder.calls, "tool_results": recorder.results}
    target = run/"workers"/(case["id"]+".json")
    observer = ModelObserver(lambda: dump(target, row))
    row["model_requests"] = observer.calls
    row["rag_answers"] = observer.rag_answers
    row["runtime_snapshots"] = observer.runtime_snapshots
    try:
        with observer.installed():
            if mode == "qa":
                from rag.rag_service import RagSummarizeService
                from langchain_core.documents import Document
                from utils.config_hander import chroma_conf
                docs = json.loads((run/"retrieval.json").read_text(encoding="utf-8"))[case["id"]]["docs"][:chroma_conf['k']]
                service = RagSummarizeService()
                evidence = [Document(page_content=d['text'], metadata=d['metadata']) for d in docs]
                inference_start = time.perf_counter()
                # Call each version's production public entry point, retaining
                # its own Runtime behavior. Only retrieval is frozen/replayed.
                with patch.object(service, "retriever_docs", return_value=evidence):
                    row["answer"] = service.rag_summarize(case["query"])
                row["inference_seconds"] = time.perf_counter()-inference_start
                row["actual_input_evidence"] = input_evidence(case, observer.calls)
            else:
                from agent.react_agent import ReactAgent
                agent = ReactAgent(user_id=case.get("user_id", ""), city=case.get("city", ""))
                if case.get("seed_history"):
                    agent.messages = seed_messages(case["seed_history"])
                    row.update(seeded_turns=case["seed_history"]["pairs"],
                               seed_history_spec=case["seed_history"],
                               seeded_history=json_value(agent.messages),
                               seed_note="Synthetic completed pairs; excluded from actual inference and task-turn counts.")
                invoke = agent.agent.invoke
                def traced(*args, **kwargs):
                    config = dict(kwargs.get("config") or {})
                    config["callbacks"] = [*config.get("callbacks", []), recorder]
                    kwargs["config"] = config
                    return invoke(*args, **kwargs)
                agent.agent.invoke = traced
                outage = patch("agent.tools.agent_tools.get_rag_service", side_effect=ConnectionError("evaluation outage")) if case.get("fault_injection") else nullcontext()
                with outage:
                    for turn in case["turns"]:
                        call_start, result_start, model_start = len(recorder.calls), len(recorder.results), len(observer.calls)
                        turn_start = time.perf_counter()
                        turn_row = {"query": turn["query"], "status": "running"}
                        row["turns"].append(turn_row)
                        dump(target, row)
                        try:
                            turn_row["answer"] = "".join(agent.execute_stream(turn["query"]))
                            turn_row["status"] = "ok"
                            if observer.calls[model_start:] and observer.calls[-1].get("incomplete"):
                                turn_row["status"] = "truncated"
                        except BaseException as exc:
                            turn_row.update(status="truncated" if type(exc).__name__ == "IncompleteModelOutput" else "error",
                                            error_type=type(exc).__name__, error=str(exc))
                            raise
                        finally:
                            calls = recorder.calls[call_start:]
                            evidence_case = dict(turn)
                            if not evidence_case.get("evidence") and turn.get("reference_ids"):
                                evidence_case["evidence"] = [e for ref in turn["reference_ids"]
                                    for e in (case_index or {}).get(ref, {}).get("evidence", [])]
                            turn_row.update(seconds=time.perf_counter()-turn_start, tool_calls=calls,
                                tool_results=recorder.results[result_start:], tool_selection=tool_selection(turn,calls),
                                model_request_indices=list(range(model_start, len(observer.calls))),
                                actual_input_evidence=input_evidence(evidence_case, observer.calls[model_start:]),
                                runtime=json_value(getattr(agent, "last_run", None)),
                                summary=json_value(getattr(agent, "summary", None)),
                                retained_messages=len(agent.messages))
                            dump(target, row)
            row["status"] = "truncated" if ((mode == "qa" and observer.calls and observer.calls[-1].get("incomplete"))
                or any(t["status"] == "truncated" for t in row["turns"])) else "ok"
    except Exception as exc:
        row.update(status="truncated" if type(exc).__name__ == "IncompleteModelOutput" else "error",
                   error_type=type(exc).__name__, error=str(exc))
        if mode == "qa":
            row["actual_input_evidence"] = input_evidence(case, observer.calls)
    row["worker_seconds"] = time.perf_counter()-start
    row["model_calls"] = recorder.models
    row["tool_calls"] = recorder.calls
    row["tool_results"] = recorder.results
    dump(target,row)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="evaluation/results/baseline_v1")
    parser.add_argument("--stage",choices=["all","retrieval","qa","agent"],default="all")
    parser.add_argument("--ids",nargs="*")
    parser.add_argument("--worker",choices=["qa","agent"])
    parser.add_argument("--case")
    parser.add_argument("--timeout",type=int,default=240)
    parser.add_argument("--dataset",default=str(DATASET))
    args=parser.parse_args()
    run=Path(args.run)
    if not run.is_absolute(): run=ROOT/run
    dataset=Path(args.dataset)
    if not dataset.is_absolute(): dataset=ROOT/dataset
    cases=verify_dataset(dataset)
    if args.worker:
        worker(args.worker,next(c for c in cases if c["id"]==args.case),run,{c["id"]: c for c in cases})
        return
    run.mkdir(parents=True,exist_ok=True)
    (run/"workers").mkdir(exist_ok=True)
    (run/"logs").mkdir(exist_ok=True)
    identity=environment_identity(dataset,args.timeout)
    code=identity["code_sha256"]
    if (run/"manifest.json").exists():
        previous=json.loads((run/"manifest.json").read_text(encoding="utf-8"))
        assert_resume_identity(previous,identity)
    else:
        dump(run/"manifest.json",{**identity,"started_at":datetime.now().astimezone().isoformat(),
            "clock_date":date.today().isoformat(),"python":sys.version,"platform":platform.platform(),
            "definition":"QA uses this version's production rag_summarize with replayed retrieval; each version retains its authorization/budget/runtime behavior. Agent runs full interactions. Synthetic history is separate from actual model requests. Semantic reviews remain independent."})
        # Keep the exact configuration and prompts for later comparisons.
        snapshot=run/"snapshot"
        (run/'cases.jsonl').write_bytes(dataset.read_bytes())
        sources=json.loads((dataset.parent/'dataset_manifest.json').read_text(encoding='utf-8'))['files']
        for name in {*code, *sources, *identity["evaluation_sha256"]}:
            source=ROOT/portable_relative_path(name)
            target=snapshot/portable_relative_path(name)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
        (snapshot/"dataset_manifest.json").write_bytes((dataset.parent/"dataset_manifest.json").read_bytes())
        if (ROOT/"variant_identity.json").exists():
            (snapshot/"variant_identity.json").write_bytes((ROOT/"variant_identity.json").read_bytes())
    selected=[c for c in cases if not args.ids or c["id"] in args.ids]
    if args.ids and set(args.ids)-{c["id"] for c in cases}:
        raise ValueError("Unknown case IDs")
    if args.stage in ("all","retrieval"):
        from rag.vector_store import VectorStoreService
        from evaluation.metrics import retrieval_metrics
        vs=VectorStoreService()
        index_stats=vs.load_document()
        dump(run/"index_check.json",index_stats)
        if index_stats["failed"]:
            raise RuntimeError("Index contains failed source documents; baseline aborted")
        existing=json.loads((run/"retrieval.json").read_text(encoding="utf-8")) if (run/"retrieval.json").exists() else {}
        for case in selected:
            if case["kind"]=="agent" or case["id"] in existing: continue
            assert_resume_identity(identity, environment_identity(dataset,args.timeout))
            start=time.perf_counter()
            docs=vs.search(case["query"],k=5)
            docs=[{"text":doc.page_content,"metadata":doc.metadata} for doc in docs]
            assert_resume_identity(identity, environment_identity(dataset,args.timeout))
            existing[case["id"]]={"docs":docs,"seconds":time.perf_counter()-start,
                "metrics":retrieval_metrics(case,docs)}
            dump(run/"retrieval.json",existing)
            print("retrieval",case["id"],existing[case["id"]]["metrics"],flush=True)
        if args.stage=="retrieval": return 0
    rows_path=run/"results.jsonl"
    if args.stage=="qa" and not (run/"retrieval.json").exists():
        raise RuntimeError("Run --stage retrieval before --stage qa")
    completed={r["id"] for r in read_rows(rows_path)} if rows_path.exists() else set()
    for case in selected:
        mode="agent" if case["kind"]=="agent" else "qa"
        if args.stage not in ("all",mode) or case["id"] in completed: continue
        start=time.perf_counter()
        # Do not mix rows after code/tool/source/model inputs change mid-run.
        assert_resume_identity(identity, environment_identity(dataset,args.timeout))
        with (run/"logs"/(case["id"]+".log")).open("w",encoding="utf-8") as log:
            command=[sys.executable,"-B","-m","evaluation.run","--worker",mode,"--case",case["id"],"--run",str(run),"--dataset",str(dataset)]
            try:
                subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                    timeout=args.timeout,check=True,env={**os.environ,"PYTHONUTF8":"1"})
                row=json.loads((run/"workers"/(case["id"]+".json")).read_text(encoding="utf-8"))
            except subprocess.TimeoutExpired:
                partial=run/"workers"/(case["id"]+".json")
                row=json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {"id":case["id"],"mode":mode,"turns":[]}
                row.update(status="timeout",error="Exceeded case wall-clock budget",worker_seconds=args.timeout)
            except Exception as exc:
                row={"id":case["id"],"mode":mode,"status":"error","error":str(exc),"turns":[]}
        row["wall_seconds"]=time.perf_counter()-start
        try:
            assert_resume_identity(identity, environment_identity(dataset,args.timeout))
        except RuntimeError as exc:
            row.update(status="error", error_type="InputsChanged", error=str(exc))
        with rows_path.open("a",encoding="utf-8") as file:
            file.write(json.dumps(row,ensure_ascii=False)+"\n")
        completed.add(case["id"])
        print(mode,case["id"],row["status"],round(row["wall_seconds"],2),flush=True)
    final_rows = {r["id"]: r for r in read_rows(rows_path)} if rows_path.exists() else {}
    planned = [c for c in selected if args.stage in ("all", "agent" if c["kind"] == "agent" else "qa")]
    return int(any(final_rows.get(c["id"], {}).get("status") != "ok" for c in planned))

if __name__=="__main__":
    raise SystemExit(main())
