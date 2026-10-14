"""Fixed failure envelopes: frozen contracts define success payloads only."""
from typing import Literal

from service_desk.contracts import StrictModel
from service_desk.db import canonical_json

MESSAGES = {
    'tool_not_allowed': '当前会话不允许此工具。',
    'arguments_invalid': '工具参数不符合公开定义。',
    'injected_argument': '身份和运行状态不能作为工具参数。',
    'schema_mismatch': '工具公开字段与校验字段不一致。',
    'identity_missing': '当前会话尚未设置用户身份。',
    'identity_mismatch': '对象不属于当前用户或不可见。',
    'session_missing': '当前会话缺少服务会话标识。',
    'slot_unavailable': '所选时段已无可用名额。',
    'slot_not_future': '只能选择业务日期之后的时段。',
    'appointment_exists': '该设备已有待上门预约，请查询或变更现有预约。',
    'error_code_not_found': '该设备型号没有相应错误码定义，请核实错误码。',
    'incompatible_consumable': '耗材与所选设备型号不兼容。',
    'out_of_stock': '库存不足，未生成订单提议。',
    'purchase_limit': '数量超过单次限购，未生成订单提议。',
    'appointment_not_scheduled': '该预约当前不能改约或取消。',
    'order_not_processing': '该订单当前不能取消。',
    'proposal_limit': '本轮最多生成两个待确认动作，请在下一轮重新提出请求。',
}


class ServiceFailure(StrictModel):
    status: Literal['denied', 'blocked']
    reason_code: str
    message: str


def failure_json(code, *, denied=False):
    value = ServiceFailure(status='denied' if denied else 'blocked',
                           reason_code=code, message=MESSAGES[code])
    return canonical_json(value.model_dump())


class PreconditionFailed(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Service precondition failed')
