"""Freeze amendment 01: scoped controls, no changes to other text fields."""
import pytest
from pydantic import ValidationError

from service_desk.contracts import (
    Consumable, Device, KnowledgeReference, LookupErrorCodeResult, MonthlyRecord,
    PendingProposal, ProposeServiceVisitArgs, RagSummarizeArgs, RagSummarizeResult,
    TicketRecord, Warranty,
)

MULTILINE = [
    (RagSummarizeArgs, 'query', {'query': '清理方法'}),
    (RagSummarizeResult, 'answer', {'answer': '先暂停'}),
    (ProposeServiceVisitArgs, 'description', {'device_id': 'D-1002-01',
        'description': '水箱不出水', 'slot_id': 'S-east-20260113-2'}),
]


@pytest.mark.parametrize('model,field,payload', MULTILINE)
def test_three_free_text_fields_keep_newlines_and_tabs_verbatim(model, field, payload):
    value = '第一段。\n\n\t第二段。'
    result = model.model_validate(payload | {field: value})
    assert getattr(result, field) == value
    assert getattr(model.model_validate_json(result.model_dump_json()), field) == value


@pytest.mark.parametrize('model,field,payload', MULTILINE)
@pytest.mark.parametrize('control', ['\r', '\x00', '\x7f', '\x0b'])
def test_free_text_still_rejects_other_controls_even_at_edges(model, field, payload, control):
    for value in (control + '正文', '正文' + control, '前文' + control + '后文'):
        with pytest.raises(ValidationError, match='control character'):
            model.model_validate(payload | {field: value})


OTHER_TEXT = [
    (LookupErrorCodeResult, 'message', {'status': 'not_found', 'definitions': []}),
    (KnowledgeReference, 'doc_ref', {'models': ['SV-200']}),
    (Warranty, 'basis', {'component': 'battery', 'in_warranty': False, 'expires_date': '2025-07-12', 'basis': '期限'}),
    (Warranty, 'reason', {'component': 'battery', 'in_warranty': False, 'expires_date': '2025-07-12', 'basis': '期限'}),
    (MonthlyRecord, '特征', {'特征': '公寓', '效率': '正常', '耗材': '滤网', '对比': '正常'}),
    (TicketRecord, 'description', {'id': 'T-1004-01', 'device_id': 'D-1004-01', 'description': '异常', 'notes': '已登记', 'status': 'scheduled'}),
    (TicketRecord, 'notes', {'id': 'T-1004-01', 'device_id': 'D-1004-01', 'description': '异常', 'notes': '已登记', 'status': 'scheduled'}),
    (Device, 'display_name', {'device_id': 'D-1002-01', 'model_code': 'SV-200', 'display_name': '扫拖',
        'serial_suffix': '0000', 'purchase_date': '2024-07-12', 'firmware': '1.0.0'}),
    (Consumable, 'name', {'sku': 'SKU-FILTER', 'kind': 'filter', 'price_cents': 3900, 'stock': 80}),
    (PendingProposal, 'summary', {'action_id': '00000000-0000-0000-0000-000000000001',
        'status': 'pending', 'args_sha256': 'a'*64, 'created_at': '2026-01-12T09:00:00+08:00',
        'expires_at': '2026-01-12T09:10:00+08:00'}),
]


@pytest.mark.parametrize('model,field,payload', OTHER_TEXT)
@pytest.mark.parametrize('control', ['\n', '\t'])
def test_other_text_fields_cannot_inherit_the_exception(model, field, payload, control):
    with pytest.raises(ValidationError, match='control character'):
        model.model_validate(payload | {field: '前文' + control + '后文'})
