"""Train one LoRA intent model and publish it to Ollama as intent-sft-<size>-<tag>.

Runs in the separate training environment (LLaMA-Factory, llama.cpp checkout),
not the application's .venv:

    python -B -m training.intent_sft.train --work E:/envirment --size 1.7B \
        --data intent_sft/data_r1 --tag r1

Stages: train (LoRA) -> merge (bf16 safetensors) -> gguf (q8_0) -> ollama.
Every stage writes into <work>/intent_sft/runs/<size>-<tag>/ with a manifest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import yaml

HERE = Path(__file__).resolve().parent
STAGES = ('train', 'merge', 'gguf', 'ollama')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, *, cwd, log):
    started = time.perf_counter()
    with open(log, 'w', encoding='utf-8') as output:
        subprocess.run([str(part) for part in command], cwd=cwd, stdout=output,
                       stderr=subprocess.STDOUT, check=True,
                       env={**os.environ, 'PYTHONUTF8': '1'})
    return round(time.perf_counter() - started, 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--size', required=True, choices=('0.6B', '1.7B', '4B'))
    parser.add_argument('--data', required=True, help='dataset dir relative to --work')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--stages', default=','.join(STAGES))
    parser.add_argument('--qlora', action='store_true', help='load the base in 4-bit')
    parser.add_argument('--set', action='append', default=[], metavar='KEY=VALUE',
                        help='override a training config value (YAML scalar)')
    args = parser.parse_args(argv)
    work = args.work.resolve()
    stages = args.stages.split(',')
    unknown = set(stages) - set(STAGES)
    if unknown:
        raise SystemExit(f'unknown stages: {sorted(unknown)}')
    name = f'intent-sft-{args.size.lower()}-{args.tag}'
    out = work / 'intent_sft' / 'runs' / f'{args.size}-{args.tag}'
    out.mkdir(parents=True, exist_ok=True)
    python = work / '.venv' / 'Scripts' / 'python.exe'
    cli = work / '.venv' / 'Scripts' / 'llamafactory-cli.exe'
    base = work / 'models' / f'Qwen3-{args.size}'
    adapter, merged, gguf = out / 'adapter', out / 'merged', out / f'{name}-q8_0.gguf'
    manifest_path = out / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest.update(ollama_name=name, size=args.size, tag=args.tag, base=str(base),
                    data=args.data, data_manifest=json.loads(
                        (work / args.data / 'manifest.json').read_text(encoding='utf-8')))
    seconds = manifest.setdefault('seconds', {})

    if 'train' in stages:
        config = yaml.safe_load((HERE / 'configs' / 'lora.yaml').read_text(encoding='utf-8'))
        config.update(model_name_or_path=str(base), dataset_dir=str(work / args.data),
                      output_dir=str(adapter))
        if args.qlora:
            config.update(quantization_bit=4, quantization_method='bnb')
        for item in args.set:
            key, value = item.split('=', 1)
            config[key] = yaml.safe_load(value)
        (out / 'train.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
        manifest['train_config'] = config
        seconds['train'] = run([cli, 'train', out / 'train.yaml'], cwd=work, log=out / 'train.log')
        results = adapter / 'all_results.json'
        manifest['train_results'] = json.loads(results.read_text(encoding='utf-8'))
    if 'merge' in stages:
        config = {'model_name_or_path': str(base), 'adapter_name_or_path': str(adapter),
                  'template': 'qwen3_nothink', 'finetuning_type': 'lora', 'trust_remote_code': True,
                  'export_dir': str(merged), 'export_size': 5, 'export_device': 'cpu',
                  'export_legacy_format': False}
        (out / 'merge.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
        seconds['merge'] = run([cli, 'export', out / 'merge.yaml'], cwd=work, log=out / 'merge.log')
    if 'gguf' in stages:
        seconds['gguf'] = run([python, work / 'tools' / 'llama.cpp' / 'convert_hf_to_gguf.py', merged,
                               '--outtype', 'q8_0', '--outfile', gguf], cwd=work, log=out / 'gguf.log')
        manifest['gguf_sha256'] = sha256(gguf)
    if 'ollama' in stages:
        template = (HERE / 'Modelfile.template').read_text(encoding='utf-8')
        (out / 'Modelfile').write_text(template.replace('{gguf}', f'./{gguf.name}'), encoding='utf-8')
        seconds['ollama'] = run(['ollama', 'create', name, '-f', 'Modelfile'], cwd=out,
                                log=out / 'ollama.log')
        if merged.exists() and gguf.exists():
            shutil.rmtree(merged)  # the GGUF and adapter are enough to rebuild it
    manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ollama_name': name, 'seconds': seconds,
                      'train_results': manifest.get('train_results')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
