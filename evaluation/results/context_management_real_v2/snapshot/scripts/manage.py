"""Entry point that also works when invoked by absolute path from another cwd."""
import argparse
from datetime import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_python(arguments):
    return subprocess.call([sys.executable, '-B', *arguments], cwd=ROOT,
                           env={**os.environ, 'PYTHONUTF8': '1'})


def dependency_checks():
    checks = []
    for line in (ROOT/'requirements-lock.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, expected = line.split('==')
        try:
            actual = importlib.metadata.version(name)
            checks.append({'name':name, 'ok':actual == expected, 'expected':expected, 'actual':actual})
        except importlib.metadata.PackageNotFoundError:
            checks.append({'name':name, 'ok':False, 'expected':expected, 'actual':'missing'})
    return checks


def doctor(offline=False):
    checks = [{'name':'Python 3.12', 'ok':sys.version_info[:2] == (3, 12), 'actual':sys.version.split()[0]}]
    checks.extend(dependency_checks())
    for name in ('config/rag.yml', 'config/chroma.yml', 'config/agent.yml', 'config/runtime.yml', 'config/context.yml', 'config/resilience.yml', 'config/security.yml', 'config/knowledge_sources.json',
                 'prompts/main_prompt.txt', 'prompts/rag_summarize.txt', 'data/external/records.csv'):
        checks.append({'name':name, 'ok':(ROOT/name).is_file()})
    model_info = []
    try:
        import yaml
        from agent.runtime import load_limits, load_resilience_policy
        load_limits()
        checks.append({'name':'runtime configuration', 'ok':True})
        load_resilience_policy()
        checks.append({'name':'resilience configuration', 'ok':True})
        from agent.context_budget import load_context_policy
        load_context_policy()
        checks.append({'name':'context configuration', 'ok':True})
        rag = yaml.safe_load((ROOT/'config/rag.yml').read_text(encoding='utf-8'))
        chroma = yaml.safe_load((ROOT/'config/chroma.yml').read_text(encoding='utf-8'))
        files = [p for p in (ROOT/chroma['data_path']).iterdir() if p.is_file() and p.suffix.lstrip('.') in chroma['allow_knowledge_file_type']]
        checks.append({'name':'knowledge files', 'ok':bool(files), 'actual':len(files)})
        from rag.security import SourceCatalog
        source_snapshot = SourceCatalog(ROOT/chroma['data_path'], ROOT/chroma['source_catalog'],
                                        policy_path=ROOT/chroma['security_policy']).snapshot()
        checks.append({'name':'knowledge source policy', 'ok':True, 'allowed':len(source_snapshot.authorized),
                       'blocked':len(source_snapshot.blocked)})
        checks.append({'name':'chunk configuration', 'ok':0 <= chroma['chunk_overlap'] < chroma['chunk_size'] and chroma['k'] > 0})
        if not offline:
            # Match the Ollama client's default environment-based host selection.
            from ollama import Client
            client = Client(timeout=10)
            models = client.list().models
            available = {m.model:m for m in models}
            for key in ('chat_model_name', 'embedding_model_name'):
                name = rag[key]
                model = available.get(name) or available.get(name+':latest')
                checks.append({'name':'Ollama '+name, 'ok':model is not None,
                               'hint':'ollama pull '+name})
                if model is not None:
                    model_info.append({'name':model.model, 'digest':model.digest, 'size_bytes':model.size})
    except Exception as exc:
        checks.append({'name':'configuration / Ollama', 'ok':False, 'error':str(exc)})
    failures = [c for c in checks if not c['ok']]
    report = {'ok':not failures, 'python':sys.executable, 'offline':offline,
              'checked':len(checks), 'failures':failures, 'models':model_info,
              'note':'只检查依赖、文件与模型可用性；不代表模型推理或回答质量通过。'}
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 1 if failures else 0


def demo(output=None):
    if doctor():
        return 1
    from evaluation.run import read_rows
    folder = Path(output) if output else ROOT/'artifacts'/('demo_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    if not folder.is_absolute():
        folder = ROOT/folder
    ids = ['A01', 'A02', 'A04', 'A09', 'A11', 'A12']
    status = run_python(['-m', 'evaluation.run', '--stage', 'agent', '--run', str(folder), '--ids', *ids])
    if status:
        return status
    rows = read_rows(folder/'results.jsonl')
    selected = {r['id']:r for r in rows if r['id'] in ids}
    complete = set(selected) == set(ids) and all(r['status'] == 'ok' for r in selected.values())
    lines = ['# 本次真实模型演示',
             '此文件是本次实际输出，不是预先录制答案。运行完成不等于语义评分通过。',
             'A12只向知识工具注入连接异常，不会关闭Ollama服务。']
    for case_id in ids:
        row = selected.get(case_id, {'status':'missing'})
        lines.append('## '+case_id+' · '+row['status'])
        if row.get('error'):
            lines.append(row['error'])
        for turn in row.get('turns', []):
            lines.extend(['问题：'+turn['query'], turn['answer'],
                          f"用时：{turn['seconds']:.2f}秒；调用："+', '.join(c['name'] for c in turn['tool_calls'])])
    (folder/'demo.md').write_text('\n\n'.join(lines), encoding='utf-8')
    print('演示记录：'+str(folder/'demo.md'), flush=True)
    return 0 if complete else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ('knowledge', 'harness'):
        module = 'scripts.knowledge' if argv[0] == 'knowledge' else 'evaluation.harness'
        return run_python(['-m', module, *argv[1:]])
    parser = argparse.ArgumentParser(description='扫地机器人客服：检查、初始化、测试、启动和真实演示')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('doctor', help='检查固定依赖、配置文件和Ollama模型')
    p.add_argument('--offline', action='store_true', help='跳过Ollama检查')
    commands.add_parser('index', help='初始化或增量更新知识库')
    commands.add_parser('test', help='运行离线回归测试')
    p = commands.add_parser('knowledge', help='知识来源管理员操作；使用 knowledge --help 查看')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    p = commands.add_parser('harness', help='离线故障/投毒评测；harness --help 查看全部选项')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    p = commands.add_parser('serve', help='启动仅本机访问的Streamlit界面')
    p.add_argument('--port', type=int, default=8501)
    p = commands.add_parser('demo', help='运行6个真实Agent案例并保存输出')
    p.add_argument('--output', help='结果目录；已有同版本案例断点续跑')
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        return doctor(args.offline)
    if args.command == 'knowledge':
        return run_python(['-m', 'scripts.knowledge', *args.arguments])
    if args.command == 'test':
        return run_python(['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    if args.command == 'index':
        return run_python(['-m', 'rag.vector_store']) if doctor() == 0 else 1
    if args.command == 'demo':
        return demo(args.output)
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    if doctor():
        return 1
    try:
        return run_python(['-m', 'streamlit', 'run', str(ROOT/'app.py'), '--server.address=127.0.0.1',
                           '--server.port='+str(args.port), '--server.headless=true', '--browser.gatherUsageStats=false'])
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
