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
import urllib.request
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation/cases.jsonl"

def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def business_files():
    paths = [ROOT/"app.py"]
    for folder in ("agent","rag","utils","model","prompts","config"):
        paths.extend(p for p in (ROOT/folder).rglob("*") if p.suffix in (".py",".txt",".yml",".json") and "__pycache__" not in p.parts)
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}

def verify_dataset(dataset=DATASET):
    dataset = Path(dataset)
    cases = read_rows(dataset)
    manifest = json.loads((dataset.parent/"dataset_manifest.json").read_text(encoding="utf-8"))
    assert digest(dataset) == manifest["dataset_sha256"], "Dataset changed; version and manifest must be updated"
    assert len({c["id"] for c in cases}) == len(cases) == manifest['case_count']
    for name, expected in manifest["files"].items():
        assert digest(ROOT/name) == expected, f"Source changed: {name}"
    for case in cases:
        for evidence in case.get("evidence", []):
            lines = (ROOT/evidence["source"]).read_text(encoding="utf-8-sig").splitlines()
            selected = "\n".join(lines[evidence["line_start"]-1:evidence["line_end"]])
            assert evidence["quote"] in selected, f"Wrong source anchor: {case['id']}"
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

def worker(mode, case, run):
    from evaluation.metrics import tool_selection
    from unittest.mock import patch
    from contextlib import nullcontext
    recorder = telemetry()
    start = time.perf_counter()
    row = {"id":case["id"], "mode":mode, "status":"ok", "turns":[]}
    try:
        if mode == "qa":
            from rag.rag_service import RagSummarizeService
            from langchain_core.documents import Document
            from utils.config_hander import chroma_conf
            docs = json.loads((run/"retrieval.json").read_text(encoding="utf-8"))[case["id"]]["docs"][:chroma_conf['k']]
            service = RagSummarizeService()
            evidence = [Document(page_content=d['text'], metadata=d['metadata']) for d in docs]
            inference_start = time.perf_counter()
            row["answer"] = service.answer_documents(case["query"], evidence, config={"callbacks":[recorder]})
            row["inference_seconds"] = time.perf_counter()-inference_start
        else:
            from agent.react_agent import ReactAgent
            agent = ReactAgent(user_id=case["user_id"], city=case["city"])
            invoke = agent.agent.invoke
            def traced(*args, **kwargs):
                config = dict(kwargs.get("config") or {})
                config["callbacks"] = [recorder]
                kwargs["config"] = config
                return invoke(*args, **kwargs)
            agent.agent.invoke = traced
            outage = patch("agent.tools.agent_tools.get_rag_service", side_effect=ConnectionError("evaluation outage")) if case.get("fault_injection") else nullcontext()
            with outage:
                for turn in case["turns"]:
                    call_start = len(recorder.calls)
                    result_start = len(recorder.results)
                    turn_start = time.perf_counter()
                    answer = "".join(agent.execute_stream(turn["query"]))
                    calls = recorder.calls[call_start:]
                    row["turns"].append({"query":turn["query"],"answer":answer,
                        "seconds":time.perf_counter()-turn_start, "tool_calls":calls,
                        "tool_results":recorder.results[result_start:],
                        "tool_selection":tool_selection(turn,calls)})
    except Exception as exc:
        row.update(status="error", error_type=type(exc).__name__, error=str(exc))
    row["worker_seconds"] = time.perf_counter()-start
    row["model_calls"] = recorder.models
    row["tool_calls"] = recorder.calls
    row["tool_results"] = recorder.results
    dump(run/"workers"/(case["id"]+".json"),row)

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
        worker(args.worker,next(c for c in cases if c["id"]==args.case),run)
        return
    run.mkdir(parents=True,exist_ok=True)
    (run/"workers").mkdir(exist_ok=True)
    (run/"logs").mkdir(exist_ok=True)
    code=business_files()
    if (run/"manifest.json").exists():
        previous=json.loads((run/"manifest.json").read_text(encoding="utf-8"))
        if previous["code_sha256"]!=code or previous["dataset_sha256"]!=digest(dataset) or previous["timeout_seconds"]!=args.timeout:
            raise RuntimeError("Cannot resume a changed baseline; choose a new --run directory.")
    else:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=10) as response:
            models=json.load(response)["models"]
        dump(run/"manifest.json",{"started_at":datetime.now().astimezone().isoformat(),
            "clock_date":date.today().isoformat(),"python":sys.version,"platform":platform.platform(),
            "dataset_sha256":digest(dataset),"code_sha256":code,
            "source_sha256":json.loads((dataset.parent/"dataset_manifest.json").read_text(encoding="utf-8"))["files"],
            "models":[{"name":m["name"],"digest":m["digest"]} for m in models],
            "dependencies":{name:importlib.metadata.version(name) for name in
                ("langchain","langchain-core","langchain-ollama","langgraph","chromadb")},
            "timeout_seconds":args.timeout,"inference_concurrency":1,
            "definition":"QA评测使用固定检索快照片段并复核当前来源授权，再调用同一RAG生成链；独立Agent场景测试完整交互。人工语义评分另存。"})
        # Keep the exact configuration and prompts for later comparisons.
        snapshot=run/"snapshot"
        (run/'cases.jsonl').write_bytes(dataset.read_bytes())
        sources=json.loads((dataset.parent/'dataset_manifest.json').read_text(encoding='utf-8'))['files']
        for name in {*code, *sources}:
            source=ROOT/name
            target=snapshot/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
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
            start=time.perf_counter()
            docs=vs.search(case["query"],k=5)
            docs=[{"text":doc.page_content,"metadata":doc.metadata} for doc in docs]
            existing[case["id"]]={"docs":docs,"seconds":time.perf_counter()-start,
                "metrics":retrieval_metrics(case,docs)}
            dump(run/"retrieval.json",existing)
            print("retrieval",case["id"],existing[case["id"]]["metrics"],flush=True)
        if args.stage=="retrieval": return
    rows_path=run/"results.jsonl"
    if args.stage=="qa" and not (run/"retrieval.json").exists():
        raise RuntimeError("Run --stage retrieval before --stage qa")
    completed={r["id"] for r in read_rows(rows_path)} if rows_path.exists() else set()
    for case in selected:
        mode="agent" if case["kind"]=="agent" else "qa"
        if args.stage not in ("all",mode) or case["id"] in completed: continue
        start=time.perf_counter()
        with (run/"logs"/(case["id"]+".log")).open("w",encoding="utf-8") as log:
            command=[sys.executable,"-B","-m","evaluation.run","--worker",mode,"--case",case["id"],"--run",str(run),"--dataset",str(dataset)]
            try:
                subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                    timeout=args.timeout,check=True,env={**os.environ,"PYTHONUTF8":"1"})
                row=json.loads((run/"workers"/(case["id"]+".json")).read_text(encoding="utf-8"))
            except subprocess.TimeoutExpired:
                row={"id":case["id"],"mode":mode,"status":"timeout","error":"Exceeded case wall-clock budget",
                     "worker_seconds":args.timeout,"turns":[]}
            except Exception as exc:
                row={"id":case["id"],"mode":mode,"status":"error","error":str(exc),"turns":[]}
        row["wall_seconds"]=time.perf_counter()-start
        with rows_path.open("a",encoding="utf-8") as file:
            file.write(json.dumps(row,ensure_ascii=False)+"\n")
        completed.add(case["id"])
        print(mode,case["id"],row["status"],round(row["wall_seconds"],2),flush=True)

if __name__=="__main__":
    main()
