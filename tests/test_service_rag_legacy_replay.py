"""Protected candidate caches prove legacy Top-5 bytes stay unchanged."""
from pathlib import Path
import hashlib
import json

from scripts.replay_service_legacy_retrieval import replay

ROOT=Path(__file__).resolve().parents[1]
BASE='90964713a92d5bf9a041fbb0fba97dc9403aa64d'


def test_both_legacy_candidate_caches_replay_without_difference():
    result=replay()
    assert result['ok'] and result['mismatches']==0 and result['variants']==3
    assert len(result['reports'])==2
    assert result['reports'][0]['queries']==49
    assert result['comparisons']==result['queries']*3


def test_legacy_rankers_and_configs_are_byte_identical_to_merged_base():
    # CI uses a shallow checkout, so pin hashes captured from the named base.
    before=json.loads((ROOT/'tests/service_rag_legacy_hashes.json').read_text(encoding='utf-8'))
    assert before['base_commit']==BASE
    for name,digest in before['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
