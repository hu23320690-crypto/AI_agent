"""S0-A public argument/result definitions only; no registered or runnable tools.

Dates are strict ISO strings so both Python dicts and JSON validate identically.
Ownership, availability and business state checks belong to S1, not this module.
"""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeviceId = Annotated[str, Field(pattern=r'^D-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$', max_length=64)]
SlotId = Annotated[str, Field(pattern=r'^S-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$', max_length=64)]
Sku = Annotated[str, Field(pattern=r'^SKU-[A-Z0-9]+(?:-[A-Z0-9]+)*$', max_length=64)]
RecordId = Annotated[str, Field(pattern=r'^[OTA]-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$', max_length=64)]
TargetId = Annotated[str, Field(pattern=r'^[OA]-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$', max_length=64)]
ModelCode = Annotated[str, Field(pattern=r'^SV-[0-9]{3}$')]
ErrorCode = Annotated[str, Field(pattern=r'^E[0-9]{2}$')]
IsoDate = Annotated[str, Field(pattern=r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')]
Month = Annotated[str, Field(pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')]
NonnegativeInt = Annotated[int, Field(ge=0)]
NonnegativeNumber = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Component = Literal['whole_machine', 'battery', 'consumables']
ConsumableKind = Literal['main_brush', 'side_brush', 'rubber_brush', 'filter', 'mop_pad', 'dust_bag']
Metric = Literal['area_m2', 'duration_min', 'error_events']
RecordKind = Literal['order', 'ticket', 'appointment']
Change = Literal['reschedule', 'cancel_appointment', 'cancel_order']


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')

    @field_validator('*')
    @classmethod
    def validate_text(cls, value, info):
        if isinstance(value, str):
            if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError('empty text or control character')
            if info.field_name in ('start', 'end', 'from_date', 'purchase_date', 'expires_date', 'date', 'business_date'):
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError('invalid ISO date')
            if info.field_name == 'month':
                date.fromisoformat(value + '-01')
            if info.field_name in ('created_at', 'expires_at', 'start_at', 'end_at'):
                if datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError('timestamp requires an explicit timezone')
        return value


class ListMyDevicesArgs(StrictModel):
    """列出本会话设备。"""
    model_config = ConfigDict(title='list_my_devices')


class LookupErrorCodeArgs(StrictModel):
    """按型号查询错误码。"""
    model_config = ConfigDict(title='lookup_error_code')
    code: ErrorCode
    device_id: DeviceId | None = None


class CheckWarrantyArgs(StrictModel):
    """查询设备部件保修。"""
    model_config = ConfigDict(title='check_warranty')
    device_id: DeviceId
    component: Component | None = None


class RagSummarizeArgs(StrictModel):
    """检索并总结维护资料。"""
    model_config = ConfigDict(title='rag_summarize')
    query: str = Field(min_length=1, max_length=3000)
    device_id: DeviceId | None = None


class FetchExternalDataArgs(StrictModel):
    """查询本会话月度记录。"""
    model_config = ConfigDict(title='fetch_external_data')
    month: Month


class GetDailyUsageArgs(StrictModel):
    """聚合至多31天用量。"""
    model_config = ConfigDict(title='get_daily_usage')
    device_id: DeviceId
    start: IsoDate
    end: IsoDate
    metric: Metric

    @model_validator(mode='after')
    def date_range(self):
        days = (date.fromisoformat(self.end) - date.fromisoformat(self.start)).days + 1
        if not 1 <= days <= 31:
            raise ValueError('inclusive date interval must be 1..31 days')
        return self


class FindServiceSlotsArgs(StrictModel):
    """查询区域可约时段。"""
    model_config = ConfigDict(title='find_service_slots')
    device_id: DeviceId
    from_date: IsoDate | None = None
    days: int = Field(default=7, ge=1, le=14)


class FindConsumablesArgs(StrictModel):
    """查询兼容耗材。"""
    model_config = ConfigDict(title='find_consumables')
    device_id: DeviceId
    kind: ConsumableKind | None = None


class GetMyOrdersAndTicketsArgs(StrictModel):
    """查询订单工单预约状态。"""
    model_config = ConfigDict(title='get_my_orders_and_tickets')
    kind: RecordKind | None = None
    id: RecordId | None = None

    @model_validator(mode='after')
    def matching_kind(self):
        if self.kind and self.id and self.id[0] != {'order': 'O', 'ticket': 'T', 'appointment': 'A'}[self.kind]:
            raise ValueError('record kind and id prefix do not match')
        return self


class ProposeServiceVisitArgs(StrictModel):
    """提议上门，等待确认。"""
    model_config = ConfigDict(title='propose_service_visit')
    device_id: DeviceId
    error_code: ErrorCode | None = None
    description: str = Field(min_length=1, max_length=1000)
    slot_id: SlotId


class ProposeOrderArgs(StrictModel):
    """提议耗材订单，等待确认。"""
    model_config = ConfigDict(title='propose_order')
    device_id: DeviceId
    sku: Sku
    qty: int = Field(ge=1)


class ProposeChangeArgs(StrictModel):
    """提议改约或取消，等待确认。"""
    model_config = ConfigDict(title='propose_change')
    target_id: TargetId
    change: Change
    new_slot_id: SlotId | None = None

    @model_validator(mode='after')
    def matching_change(self):
        if self.change == 'reschedule':
            if not self.target_id.startswith('A-') or self.new_slot_id is None:
                raise ValueError('reschedule requires appointment and new slot')
        else:
            prefix = 'O-' if self.change == 'cancel_order' else 'A-'
            if not self.target_id.startswith(prefix) or self.new_slot_id is not None:
                raise ValueError('cancel target mismatch or unexpected slot')
        return self


class Device(StrictModel):
    device_id: DeviceId
    model_code: ModelCode
    display_name: str
    serial_suffix: str = Field(min_length=1, max_length=8)
    purchase_date: IsoDate
    firmware: str


class ListMyDevicesResult(StrictModel):
    devices: list[Device]


class ErrorDefinition(StrictModel):
    model_code: ModelCode
    code: ErrorCode
    title: str
    severity: int = Field(ge=1, le=3)
    self_fixable: bool
    requires_visit: bool
    doc_ref: str


class LookupErrorCodeResult(StrictModel):
    status: Literal['ok', 'not_found', 'clarify']
    definitions: list[ErrorDefinition]
    message: str | None = None


class Warranty(StrictModel):
    component: Component
    in_warranty: bool
    expires_date: IsoDate
    basis: str
    reason: str | None = None


class CheckWarrantyResult(StrictModel):
    device_id: DeviceId
    business_date: IsoDate
    coverage: list[Warranty]


class KnowledgeReference(StrictModel):
    doc_ref: str
    models: list[ModelCode | Literal['all']]


class RagSummarizeResult(StrictModel):
    # The legacy text is preserved verbatim inside this structured envelope.
    answer: str
    references: list[KnowledgeReference] = Field(default_factory=list)


class MonthlyRecord(StrictModel):
    model_config = ConfigDict(populate_by_name=True)
    features: str = Field(alias='特征')
    efficiency: str = Field(alias='效率')
    consumables: str = Field(alias='耗材')
    comparison: str = Field(alias='对比')


class FetchExternalDataResult(StrictModel):
    # model_dump(by_alias=True, exclude_none=True) retains the legacy shape.
    status: Literal['ok', 'not_found']
    user_id: str
    month: Month
    data: MonthlyRecord | None = None
    message: str | None = None

    @model_validator(mode='after')
    def status_payload(self):
        if self.status == 'ok' and (self.data is None or self.message is not None):
            raise ValueError('ok requires data and no message')
        if self.status == 'not_found' and (self.message is None or self.data is not None):
            raise ValueError('not_found requires message and no data')
        return self


class GetDailyUsageResult(StrictModel):
    device_id: DeviceId
    start: IsoDate
    end: IsoDate
    metric: Metric
    days_observed: int = Field(ge=0, le=31)
    total: NonnegativeNumber
    daily_average: NonnegativeNumber
    maximum: NonnegativeNumber


class ServiceSlot(StrictModel):
    slot_id: SlotId
    region: str
    start_at: str
    end_at: str
    available: int = Field(ge=1)


class FindServiceSlotsResult(StrictModel):
    device_id: DeviceId
    slots: list[ServiceSlot]


class Consumable(StrictModel):
    sku: Sku
    name: str
    kind: ConsumableKind
    price_cents: NonnegativeInt
    stock: NonnegativeInt
    max_per_order: int | None = Field(default=None, ge=1)


class FindConsumablesResult(StrictModel):
    device_id: DeviceId
    consumables: list[Consumable]


class OrderRecord(StrictModel):
    kind: Literal['order'] = 'order'
    id: Annotated[str, Field(pattern=r'^O-[A-Za-z0-9-]+$')]
    device_id: DeviceId
    sku: Sku
    qty: int = Field(ge=1)
    amount_cents: NonnegativeInt
    status: Literal['processing', 'completed', 'cancelled']


class TicketRecord(StrictModel):
    kind: Literal['ticket'] = 'ticket'
    id: Annotated[str, Field(pattern=r'^T-[A-Za-z0-9-]+$')]
    device_id: DeviceId
    error_code: ErrorCode | None = None
    description: str
    notes: str
    status: Literal['processing', 'completed', 'scheduled', 'cancelled']


class AppointmentRecord(StrictModel):
    kind: Literal['appointment'] = 'appointment'
    id: Annotated[str, Field(pattern=r'^A-[A-Za-z0-9-]+$')]
    ticket_id: Annotated[str, Field(pattern=r'^T-[A-Za-z0-9-]+$')]
    slot_id: SlotId
    status: Literal['scheduled', 'completed', 'cancelled']


class GetMyOrdersAndTicketsResult(StrictModel):
    records: list[Annotated[OrderRecord | TicketRecord | AppointmentRecord, Field(discriminator='kind')]]


class PendingProposal(StrictModel):
    action_id: Annotated[str, Field(pattern=r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')]
    status: Literal['pending']
    args_sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    summary: str
    created_at: str
    expires_at: str


class ProposeServiceVisitResult(PendingProposal):
    tool: Literal['propose_service_visit']
    args: ProposeServiceVisitArgs


class ProposeOrderResult(PendingProposal):
    tool: Literal['propose_order']
    args: ProposeOrderArgs
    amount_cents: NonnegativeInt


class ProposeChangeResult(PendingProposal):
    tool: Literal['propose_change']
    args: ProposeChangeArgs


ARGUMENT_MODELS = {
    'list_my_devices': ListMyDevicesArgs, 'lookup_error_code': LookupErrorCodeArgs,
    'check_warranty': CheckWarrantyArgs, 'rag_summarize': RagSummarizeArgs,
    'fetch_external_data': FetchExternalDataArgs, 'get_daily_usage': GetDailyUsageArgs,
    'find_service_slots': FindServiceSlotsArgs, 'find_consumables': FindConsumablesArgs,
    'get_my_orders_and_tickets': GetMyOrdersAndTicketsArgs,
    'propose_service_visit': ProposeServiceVisitArgs, 'propose_order': ProposeOrderArgs,
    'propose_change': ProposeChangeArgs,
}
RESULT_MODELS = {
    'list_my_devices': ListMyDevicesResult, 'lookup_error_code': LookupErrorCodeResult,
    'check_warranty': CheckWarrantyResult, 'rag_summarize': RagSummarizeResult,
    'fetch_external_data': FetchExternalDataResult, 'get_daily_usage': GetDailyUsageResult,
    'find_service_slots': FindServiceSlotsResult, 'find_consumables': FindConsumablesResult,
    'get_my_orders_and_tickets': GetMyOrdersAndTicketsResult,
    'propose_service_visit': ProposeServiceVisitResult, 'propose_order': ProposeOrderResult,
    'propose_change': ProposeChangeResult,
}
SERVICE_TOOL_NAMES = tuple(ARGUMENT_MODELS)
READ_TOOLS = frozenset(SERVICE_TOOL_NAMES[:9])
WRITE_PROPOSAL_TOOLS = frozenset(SERVICE_TOOL_NAMES[9:])
