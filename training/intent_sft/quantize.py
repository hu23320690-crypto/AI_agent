"""Q4_K_M export of a trained intent SFT adapter (supplementary E6).

The main runs export q8_0 while the qwen3:4b baseline is Q4_K_M. This merges an
existing run's adapter again, converts it to f16, quantizes it with llama.cpp's
llama-quantize and registers it with Ollama as <run name>-q4km. The original
run directory is not modified.

    python -B -m training.intent_sft.quantize --work E:/envirment --size 1.7B --tag r2 \
        --quantizer E:/envirment/tools/llama-bin/llama-quantize.exe
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from training.intent_sft.train import HERE, run, sha256


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--size', required=True, choices=('0.6B', '1.7B', '4B'))
    parser.add_argument('--tag', required=True)
    parser.add_argument('--quantizer', required=True, type=Path)
    parser.add_argument('--type', default='Q4_K_M')
    args = parser.parse_args(argv)
    import yaml
    work = args.work.resolve()
    source = work / 'intent_sft' / 'runs' / f'{args.size}-{args.tag}'
    suffix = args.type.lower().replace('_', '')
    name = f'intent-sft-{args.size.lower()}-{args.tag}-{suffix}'
    out = source.with_name(f'{source.name}-{suffix}')
    out.mkdir(parents=True, exist_ok=True)
    python = work / '.venv' / 'Scripts' / 'python.exe'
    cli = work / '.venv' / 'Scripts' / 'llamafactory-cli.exe'
    merged, f16, gguf = out / 'merged', out / f'{name}-f16.gguf', out / f'{name}.gguf'
    # The same merge settings as train.py, onto the bf16 base.
    config = {'model_name_or_path': str(work / 'models' / f'Qwen3-{args.size}'),
              'adapter_name_or_path': str(source / 'adapter'), 'template': 'qwen3_nothink',
              'finetuning_type': 'lora', 'trust_remote_code': True, 'export_dir': str(merged),
              'export_size': 5, 'export_device': 'cpu', 'export_legacy_format': False}
    (out / 'merge.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
    seconds = {'merge': run([cli, 'export', out / 'merge.yaml'], cwd=work, log=out / 'merge.log')}
    seconds['gguf_f16'] = run([python, work / 'tools' / 'llama.cpp' / 'convert_hf_to_gguf.py',
                               merged, '--outtype', 'f16', '--outfile', f16], cwd=work,
                              log=out / 'gguf.log')
    seconds['quantize'] = run([args.quantizer, f16, gguf, args.type], cwd=out,
                              log=out / 'quantize.log')
    shutil.rmtree(merged)
    f16.unlink()
    template = (HERE / 'Modelfile.template').read_text(encoding='utf-8')
    (out / 'Modelfile').write_text(template.replace('{gguf}', f'./{gguf.name}'), encoding='utf-8')
    seconds['ollama'] = run(['ollama', 'create', name, '-f', 'Modelfile'], cwd=out,
                            log=out / 'ollama.log')
    manifest = {'ollama_name': name, 'source_run': source.name, 'type': args.type,
                'source_manifest': json.loads((source / 'manifest.json').read_text(encoding='utf-8')),
                'quantizer': str(args.quantizer), 'quantizer_sha256': sha256(args.quantizer),
                'gguf_sha256': sha256(gguf), 'gguf_bytes': gguf.stat().st_size,
                'seconds': seconds, 'updated_at': datetime.now(timezone.utc).isoformat()}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding='utf-8')
    print(json.dumps({key: manifest[key] for key in ('ollama_name', 'gguf_bytes', 'seconds')}))


if __name__ == '__main__':
    main()
