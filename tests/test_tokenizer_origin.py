"""An operator may explicitly trust one container Ollama origin, never user input."""
import os
from unittest.mock import patch

import pytest

from model.token_count import _local_client


@pytest.mark.parametrize('host', ['http://remote:11434', 'https://example.com'])
def test_nonlocal_origin_denied_by_default(host):
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError):
        _local_client(host, 1)


def test_explicit_exact_container_origin_and_loopback():
    with patch.dict(os.environ, {'TOKENIZER_ALLOWED_ORIGIN': 'http://ollama:11434'}, clear=True):
        for host in ('http://ollama:11434/', 'http://127.0.0.1:11434'):
            with _local_client(host, 1) as client:
                assert client.base_url.host in ('ollama', '127.0.0.1')


@pytest.mark.parametrize('host', [
    'http://ollama:11435', 'https://ollama:11434', 'http://other:11434',
    'http://user:password@ollama:11434', 'http://ollama:11434/prefix',
    'http://ollama:11434/?q=1', 'http://ollama:11434/#fragment',
    'file:///tmp/model', 'http://ollama:invalid', 'http://@127.0.0.1:11434',
])
def test_opt_in_does_not_widen_trust(host):
    with patch.dict(os.environ, {'TOKENIZER_ALLOWED_ORIGIN': 'http://ollama:11434'}, clear=True):
        with pytest.raises(ValueError):
            _local_client(host, 1)
