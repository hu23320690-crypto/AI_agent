"""Build a source-only delivery ZIP with an explicit file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('README.md', 'requirements.txt', 'requirements-lock.txt', '.python-version', '.gitignore', 'app.py')
DIRECTORIES = ('agent', 'rag', 'model', 'utils', 'config', 'prompts', 'data', 'tests', 'scripts', 'docs', 'evaluation')
EVIDENCE = ('artifacts/runtime_stage4_retrieval_dev/ablation.json',
            'artifacts/runtime_stage4_retrieval_dev/candidate_cache.json',
            'artifacts/runtime_stage4_retrieval_holdout/ablation.json',
            'artifacts/runtime_stage4_retrieval_holdout/candidate_cache.json',
            'artifacts/runtime_stage4_retrieval_trials/ablation_trial_v1.json',
            'artifacts/runtime_stage4_retrieval_trials/ablation_source_coverage_trials.json',
            'artifacts/runtime_stage4_retrieval_trials/ablation_rrf_weight_exploration.json',
            'artifacts/context_management_v1/doctor_final.json',
            'artifacts/context_management_v1/regression_summary.json',
            'artifacts/context_management_v1/regression_final.log',
            'artifacts/context_management_v1/delivery.json',
            'artifacts/github_publication_v1/doctor_offline.json',
            'artifacts/github_publication_v1/regression.log',
            'artifacts/github_publication_v1/checks.json')
EXCLUDED = {'__pycache__', 'chroma_db', 'logs', 'workers', '.venv', '.git'}


def selected_files():
    files = [ROOT/name for name in FILES if (ROOT/name).is_file()]
    for directory in DIRECTORIES:
        for path in (ROOT/directory).rglob('*'):
            relative = path.relative_to(ROOT)
            if path.is_file() and not path.is_symlink() and not any(part in EXCLUDED for part in relative.parts):
                if path.suffix not in ('.pyc', '.pyo', '.lock', '.tmp', '.key', '.pem', '.p12', '.pfx') and not path.name.startswith('.env') and path.name != 'secrets.toml':
                    files.append(path)
    files.extend(ROOT/name for name in EVIDENCE if (ROOT/name).is_file())
    return sorted(set(files))


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('交付文件已存在，请指定新的输出文件名：'+str(output))
    files = selected_files()
    if output in files:
        raise ValueError('输出文件不能是项目输入文件')
    hashes = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'AI_agent/'+path.relative_to(ROOT).as_posix())
        archive.writestr('AI_agent/DELIVERY_MANIFEST.json', json.dumps({'files':hashes},ensure_ascii=False,indent=2))
    print(json.dumps({'path':str(output), 'files':len(files), 'bytes':output.stat().st_size,
                      'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成源码交付包，不包含环境、向量库、日志或模型')
    parser.add_argument('--output', default=str(ROOT/'dist/AI_agent_source.zip'))
    args = parser.parse_args()
    build(args.output)
