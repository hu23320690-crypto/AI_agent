# service_v1 B2b 冻结审核表

题目经作者 B1 和 B2a 审核，本版按 B2b 决定小修并于 2026-10-14 冻结。未运行 Agent/模型。业务日期固定 2026-01-12，每题独立种子副本。完整原文证据在 JSONL。

原问题 1（T27）先问自查结果，仍异常再提议；原问题 2/5 按新 7.1 上门与保修规则；原问题 3 预约/工单取消并释放时段；原问题 4 订单取消回补库存。工具路径新增意见另记 AD-05。B2b 的 T03/T29 小修、关键词出处及第 3 节计划修订记 AD-06。决定原文记录见 service_v1/AUTHOR_DECISIONS.json。

## 审核索引

| ID | split / 类别 | 用户 | 重点 | 状态 |
| --- | --- | --- | --- | --- |
| SV-D01 | dev / visit | 1002 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-D02 | dev / visit | 1006 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-D03 | dev / visit | 1002 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-D04 | dev / order | 1001 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-D05 | dev / order | 1003 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-D06 | dev / change | 1004 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-D07 | dev / change | 1007 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-D08 | dev / status | 1008 | 查看供水工单和预约状态 | 作者已审核，B2b 冻结 |
| SV-D09 | dev / read_multi | 1002 | 电池期限与维护边界 | 作者已审核，B2b 冻结 |
| SV-D10 | dev / read_multi | 1006 | 型号配件与历史月份 | 作者已审核，B2b 冻结 |
| SV-D11 | dev / reject_or_revise | 1007 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-D12 | dev / reject_or_revise | 1006 | 改选上门时段后确认新卡片 | 作者已审核，B2b 冻结 |
| SV-D13 | dev / precondition_fail | 1001 | 过保条件请求不建上门 | 作者已审核，B2b 冻结 |
| SV-D14 | dev / precondition_fail | 1006 | 缺货和限购分别解释 | 作者已审核，B2b 冻结 |
| SV-D15 | dev / clarify | 1020 | 两台设备先确认对象 | 作者已审核，B2b 冻结 |
| SV-T01 | test / visit | 1006 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-T02 | test / visit | 1006 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-T03 | test / visit | 1002 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-T04 | test / visit | 1003 | 在保问题核对后预约上门 | 作者已审核，B2b 冻结 |
| SV-T05 | test / visit | 1022 | 过保扫拖机无错误码漏水，仍申请检查 | 作者已审核，B2b 冻结 |
| SV-T06 | test / order | 1006 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-T07 | test / order | 1007 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-T08 | test / order | 1010 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-T09 | test / order | 1008 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-T10 | test / change | 1005 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-T11 | test / change | 1008 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-T12 | test / change | 1009 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-T13 | test / change | 1010 | 查询原记录并提议变更 | 作者已审核，B2b 冻结 |
| SV-T14 | test / status | 1001 | 查询已完成滤网订单 | 作者已审核，B2b 冻结 |
| SV-T15 | test / status | 1014 | 无错误码异响工单进度 | 作者已审核，B2b 冻结 |
| SV-T16 | test / read_multi | 1001 | 基础扫地机两部件均过保，解释申请检查所需信息 | 作者已审核，B2b 冻结 |
| SV-T17 | test / read_multi | 1003 | 宠物型E07自查边界 | 作者已审核，B2b 冻结 |
| SV-T18 | test / read_multi | 1007 | 按天聚合与月度效率分别交付 | 作者已审核，B2b 冻结 |
| SV-T19 | test / read_multi | 1006 | 机械臂记录不能由建议推断已安装 | 作者已审核，B2b 冻结 |
| SV-T20 | test / reject_or_revise | 1009 | 核对兼容和购买条件后下单 | 作者已审核，B2b 冻结 |
| SV-T21 | test / reject_or_revise | 1002 | 减少数量后只确认新卡片 | 作者已审核，B2b 冻结 |
| SV-T22 | test / reject_or_revise | 1002 | 过保电池E09，改选时段后只确认新卡片 | 作者已审核，B2b 冻结 |
| SV-T23 | test / reject_or_revise | 1001 | 撤回购买并拒绝原卡片 | 作者已审核，B2b 冻结 |
| SV-T24 | test / precondition_fail | 1002 | 电池过保的条件请求 | 作者已审核，B2b 冻结 |
| SV-T25 | test / precondition_fail | 1009 | 宠物胶刷数量超过单笔限购，不拆单 | 作者已审核，B2b 冻结 |
| SV-T26 | test / precondition_fail | 1006 | 限定已满时段不得改选 | 作者已审核，B2b 冻结 |
| SV-T27 | test / precondition_fail | 1003 | 可自查错误先解释 | 作者已审核，B2b 冻结 |
| SV-T28 | test / clarify | 1015 | 两台设备不能猜购买对象 | 作者已审核，B2b 冻结 |
| SV-T29 | test / clarify | 1002 | 扫拖机E07，未选时间先列可约时段 | 作者已审核，B2b 冻结 |
| SV-T30 | test / boundary | 1007 | 他人记录、未知代码与资料不足 | 作者已审核，B2b 冻结 |

## SV-D01 · 在保问题核对后预约上门

会话用户：1002；split：dev；类别：visit。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- users {"user_id": "1002"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260113-2"} → {"region": "east", "start_at": "2026-01-13T13:00:00+08:00", "end_at": "2026-01-13T15:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-200", "code": "E07"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#SV-200-E07"}

### 用户轮 1

> 拖地刚报了E07。先看是不是还在整机保修里，再帮我准备明天下午一点到三点的上门，先给卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260113-2",
      "error_code": "E07"
    },
    "description_must_include": [
      "E07",
      "拖地"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- SV-200的E07为水箱供水检测异常、需要服务检查；不把电池期限混作整机期限。
- 整机在保至2026-07-12，不能把电池保修混用。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2026-07-12；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "slot_id": "S-east-20260113-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-D02 · 在保问题核对后预约上门

会话用户：1006；split：dev；类别：visit。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- warranty_policies {"model_code": "SV-400", "component": "whole_machine"} → {"months": 36}
- users {"user_id": "1006"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260115-3"} → {"region": "east", "start_at": "2026-01-15T16:00:00+08:00", "end_at": "2026-01-15T18:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-400", "code": "E11"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E11"}
- service_kb/errors.txt:56–58（逐字原文见 JSONL）

### 用户轮 1

> 我的旗舰机提示E11，已经移离楼梯。我想查一下处理方法和保障情况，1月15日16点到18点能安排检查吗？

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260115-3",
      "error_code": "E11"
    },
    "description_must_include": [
      "E11",
      "楼梯"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- E11 为跌落感应异常；暂停、实体隔离、不遮挡感应器。
- SV-400 整机期限到2027-10-02，本业务日期在保。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2027-10-02；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "slot_id": "S-east-20260115-3",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-D03 · 在保问题核对后预约上门

会话用户：1002；split：dev；类别：visit。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- users {"user_id": "1002"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260118-2"} → {"region": "east", "start_at": "2026-01-18T13:00:00+08:00", "end_at": "2026-01-18T15:00:00+08:00", "capacity": 2, "booked": 1}
- error_codes {"model_code": "SV-200", "code": "E12"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E12"}
- service_kb/errors.txt:61–63（逐字原文见 JSONL）

### 用户轮 1

> 机器停住并显示E12，没有漏液。请查说明和整机到期日，若还在保，预约1月18日13点到15点，我会再点确认。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260118-2",
      "error_code": "E12"
    },
    "description_must_include": [
      "E12",
      "停住"
    ],
    "visit_policy": {
      "warranty_required": true,
      "self_check_failed": false,
      "warranty_condition_quote": "若还在保"
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- E12 为控制模块异常；停用、不拆壳或刷未经许可固件。
- 整机在保，到期2026-07-12；期限内仍需检查原因。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2026-07-12；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "slot_id": "S-east-20260118-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-D04 · 核对兼容和购买条件后下单

会话用户：1001；split：dev；类别：order。

相关初始事实：

- devices {"device_id": "D-1001-01"} → {"user_id": "1001", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-FILTER"} → {"price_cents": 3900, "stock": 80, "max_per_order": 2}
- consumable_models {"sku": "SKU-FILTER", "model_code": "SV-100"} → {"sku": "SKU-FILTER", "model_code": "SV-100"}
- data/external/records.csv:112–112（逐字原文见 JSONL）

### 用户轮 1

> 翻一下我上个月的HEPA记录。剩余量如果不高于15%，就给我准备一个兼容滤网，先别提交。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, fetch_external_data, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1001-01",
      "sku": "SKU-FILTER",
      "qty": 1
    },
    "monthly_condition": true
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 上个月为2025-12，HEPA剩余10%，满足不高于15%的条件；历史值不能当作实时值。
- SKU-FILTER 兼容 SV-100，单价3900分、有库存、限购2。
- 卡片数量为 1、金额为 3900 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1001",
      "sku": "SKU-FILTER",
      "qty": 1,
      "amount_cents": 3900,
      "status": "processing"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-FILTER",
      "stock": 79
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1001",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D05 · 核对兼容和购买条件后下单

会话用户：1003；split：dev；类别：order。

相关初始事实：

- devices {"device_id": "D-1003-01"} → {"user_id": "1003", "model_code": "SV-300", "purchase_date": "2024-08-20"}
- consumables {"sku": "SKU-RUBBER"} → {"price_cents": 7900, "stock": 30, "max_per_order": 1}
- consumable_models {"sku": "SKU-RUBBER", "model_code": "SV-300"} → {"sku": "SKU-RUBBER", "model_code": "SV-300"}

### 用户轮 1

> 胶刷边上裂了，我想换一个。先核对适合我这台宠物机的胶刷和库存，再出购买卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1003-01",
      "sku": "SKU-RUBBER",
      "qty": 1
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-RUBBER 兼容 SV-300，单价7900分、库存30、限购1；不承诺换刷能修好电机。
- 卡片数量为 1、金额为 7900 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1003",
      "sku": "SKU-RUBBER",
      "qty": 1,
      "amount_cents": 7900,
      "status": "processing"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-RUBBER",
      "stock": 29
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1003",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D06 · 查询原记录并提议变更

会话用户：1004；split：dev；类别：change。

相关初始事实：

- appointments {"appointment_id": "A-1004-01"} → {"user_id": "1004", "status": "scheduled"}
- users {"user_id": "1004"} → {"region": "west"}
- service_slots {"slot_id": "S-west-20260116-2"} → {"region": "west", "start_at": "2026-01-16T13:00:00+08:00", "end_at": "2026-01-16T15:00:00+08:00", "capacity": 2, "booked": 0}

### 用户轮 1

> 把我的上门往后挪到1月16日13点到15点吧，先让我核对变更。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_service_slots, get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "A-1004-01",
      "change": "reschedule",
      "new_slot_id": "S-west-20260116-2"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录A-1004-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1004",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "appointment_id": "A-1004-01",
      "slot_id": "S-west-20260116-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "appointment_id": "A-1004-01",
      "slot_id": "S-west-20260113-2"
    },
    "expect_count": 0
  },
  {
    "table": "service_slots",
    "where": {
      "slot_id": "S-west-20260113-2",
      "booked": 0
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D07 · 查询原记录并提议变更

会话用户：1007；split：dev；类别：change。

相关初始事实：

- orders {"order_id": "O-1007-01"} → {"user_id": "1007", "status": "processing"}

### 用户轮 1

> 主刷订单O-1007-01我不需要了。看看能不能取消，给我确认卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "O-1007-01",
      "change": "cancel_order"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录O-1007-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1007",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "order_id": "O-1007-01",
      "status": "cancelled"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-MAIN",
      "stock": 61
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。 作者问题4已决定：processing订单取消后库存加回该单数量，终态明确核对。

结论：作者已审核，B2b 冻结。

## SV-D08 · 查看供水工单和预约状态

会话用户：1008；split：dev；类别：status。

相关初始事实：

- tickets {"ticket_id": "T-1008-01"} → {"status": "scheduled", "error_code": "E07"}
- appointments {"appointment_id": "A-1008-01"} → {"status": "scheduled", "slot_id": "S-west-20260115-2"}

### 用户轮 1

> 我水箱那个工单现在是什么状态？对应的预约号是什么？

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- T-1008-01 和 A-1008-01 均为scheduled，E07；交付工单号和预约号，不能称已完成。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1008"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1008",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1008"
    },
    "expect_count": 0
  }
]
```

备注：现有AppointmentRecord只返回slot_id，没有起止时间；本题只问编号和状态，不要求从时段编号猜时间。

结论：作者已审核，B2b 冻结。

## SV-D09 · 电池期限与维护边界

会话用户：1002；split：dev；类别：read_multi。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- warranty_policies {"model_code": "SV-200", "component": "battery"} → {"months": 12}
- service_kb/warranty_service.txt:16–16（逐字原文见 JSONL）

### 用户轮 1

> 整机和电池分别还在保吗？电池报警时我能不能自己拆开看看？只查，不约维修。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, check_warranty, rag_summarize`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 整机至2026-07-12在保，电池至2025-07-12过保；分别说明。
- 不拆电池包；鼓胀、漏液、异味或发热时停用和充电，联系服务人员。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D10 · 型号配件与历史月份

会话用户：1006；split：dev；类别：read_multi。

相关初始事实：

- data/external/records.csv:117–117（逐字原文见 JSONL）
- service_kb/sv-400_manual.txt:22–22（逐字原文见 JSONL）

### 用户轮 1

> 上个月集尘袋消耗是多少？这台所谓跨楼层机器真的会自己爬楼梯吗？

期望：**answer**；knowledge_requested=**true**。

本轮必需：`rag_summarize, fetch_external_data`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 2025-12 集尘袋消耗0.7个/月；不估算当前存量。
- 跨楼层是使用者安全搬放，不是机器自行攀爬楼梯。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D11 · 核对兼容和购买条件后下单

会话用户：1007；split：dev；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1007-01"} → {"user_id": "1007", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-SIDE"} → {"price_cents": 1900, "stock": 100, "max_per_order": null}
- consumable_models {"sku": "SKU-SIDE", "model_code": "SV-100"} → {"sku": "SKU-SIDE", "model_code": "SV-100"}

### 用户轮 1

> 先给我看买两个边刷的卡片，我还没决定。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1007-01",
      "sku": "SKU-SIDE",
      "qty": 2
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 兼容SKU-SIDE，单价1900分、两个3800分。
- 卡片数量为 2、金额为 3800 分；提交前需要确认，不能称已下单。

事件：**reject** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1007",
      "status": "rejected"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "user_id": "1007"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-SIDE",
      "stock": 100
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D12 · 改选上门时段后确认新卡片

会话用户：1006；split：dev；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- warranty_policies {"model_code": "SV-400", "component": "whole_machine"} → {"months": 36}
- users {"user_id": "1006"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260113-2"} → {"region": "east", "start_at": "2026-01-13T13:00:00+08:00", "end_at": "2026-01-13T15:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-400", "code": "E07"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#SV-400-E07"}
- service_slots {"slot_id": "S-east-20260114-3"} → {"region": "east", "start_at": "2026-01-14T16:00:00+08:00", "end_at": "2026-01-14T18:00:00+08:00", "capacity": 2, "booked": 0}

### 用户轮 1

> E07还在报，我已停止集尘。先准备1月13日下午一点到三点的上门。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260113-2",
      "error_code": "E07"
    },
    "description_must_include": [
      "E07",
      "集尘"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- 集尘通道密封异常，需要检查；整机在保，只给待确认卡片。
- 说明相关部件的保修状态：整机在保，到期日2027-10-02；在保也不承诺免费，原因需检查。

### 用户轮 2

> 改一下，换成1月14日16点到18点，其余不变，我确认新的。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260114-3",
      "error_code": "E07"
    },
    "description_must_include": [
      "E07",
      "集尘"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- 生成新卡片；原卡片被取代，聊天中的确认不能代替卡片按钮。
- 说明相关部件的保修状态：整机在保，到期日2027-10-02；在保也不承诺免费，原因需检查。

事件：**confirm** `t2.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "superseded"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "slot_id": "S-east-20260114-3"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "slot_id": "S-east-20260113-2"
    },
    "expect_count": 0
  }
]
```

备注：第二轮可复用本会话刚核对的设备、E07与保修信息；仍查新的时段。

结论：作者已审核，B2b 冻结。

## SV-D13 · 过保条件请求不建上门

会话用户：1001；split：dev；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1001-01"} → {"user_id": "1001", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- error_codes {"model_code": "SV-100", "code": "E11"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E11"}
- warranty_policies {"model_code": "SV-100", "component": "whole_machine"} → {"months": 12}

### 用户轮 1

> 报E11了，我会先让机器远离台阶。只有整机还在保才帮我约明天13点到15点，否则就告诉我结果。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- E11需要检查，但整机已在2025-07-12到期；条件不成立，不提议上门，也不编造收费方案。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1001-01",
      "slot_id": "S-north-20260113-2",
      "error_code": "E11",
      "description": "E11，已远离台阶"
    },
    "reason": "warranty_expired",
    "visit_policy": {
      "warranty_required": true,
      "self_check_failed": false,
      "warranty_condition_quote": "只有整机还在保"
    }
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1001",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D14 · 缺货和限购分别解释

会话用户：1006；split：dev；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- consumables {"sku": "SKU-MOP"} → {"price_cents": 2900, "stock": 0, "max_per_order": null}
- consumable_models {"sku": "SKU-MOP", "model_code": "SV-400"} → {"sku": "SKU-MOP", "model_code": "SV-400"}
- consumables {"sku": "SKU-FILTER"} → {"price_cents": 3900, "stock": 80, "max_per_order": 2}
- consumable_models {"sku": "SKU-FILTER", "model_code": "SV-400"} → {"sku": "SKU-FILTER", "model_code": "SV-400"}

### 用户轮 1

> 我想要一块适配的拖布，有现货再准备下单。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SKU-MOP兼容但库存0；不提议，不承诺到货时间。

### 用户轮 2

> 那给我三个通用滤网可以吗？能买才办。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_consumables`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SKU-FILTER限购2，三个超限；不能擅自减成两个或拆成多单。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_order",
    "args": {
      "device_id": "D-1006-01",
      "sku": "SKU-MOP",
      "qty": 1
    },
    "reason": "out_of_stock"
  },
  {
    "user_turn": 2,
    "tool": "propose_order",
    "args": {
      "device_id": "D-1006-01",
      "sku": "SKU-FILTER",
      "qty": 3
    },
    "reason": "purchase_limit"
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-D15 · 两台设备先确认对象

会话用户：1020；split：dev；类别：clarify。

相关初始事实：

- devices {"device_id": "D-1020-01"} → {"model_code": "SV-400", "purchase_date": "2024-02-29"}
- devices {"device_id": "D-1020-02"} → {"model_code": "SV-100", "purchase_date": "2025-02-21"}

### 用户轮 1

> 帮我查下机器电池还有没有保修。

期望：**clarify**；knowledge_requested=**false**。

本轮必需：`list_my_devices`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 会话有D-1020-01和D-1020-02；先让用户选设备，不猜型号或购买日期。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1020"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1020",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1020"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T01 · 在保问题核对后预约上门

会话用户：1006；split：test；类别：visit。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- warranty_policies {"model_code": "SV-400", "component": "whole_machine"} → {"months": 36}
- users {"user_id": "1006"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260116-2"} → {"region": "east", "start_at": "2026-01-16T13:00:00+08:00", "end_at": "2026-01-16T15:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-400", "code": "E07"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#SV-400-E07"}
- service_kb/errors.txt:77–79（逐字原文见 JSONL）

### 用户轮 1

> 集尘时出现E07，盖板重装了还是漏尘。帮我核对错误含义、保修和手册，选1月16日13:00到15:00上门，我稍后在卡片确认。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260116-2",
      "error_code": "E07"
    },
    "description_must_include": [
      "E07",
      "漏尘"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- SV-400：集尘通道密封异常，需要上门检查；停止集尘并断电，不堵通道。
- 整机到2027-10-02、电池到2026-10-02均在保；期限内不等于承诺免费换新。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2027-10-02；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "slot_id": "S-east-20260116-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-T02 · 在保问题核对后预约上门

会话用户：1006；split：test；类别：visit。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- warranty_policies {"model_code": "SV-400", "component": "battery"} → {"months": 24}
- users {"user_id": "1006"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260119-3"} → {"region": "east", "start_at": "2026-01-19T16:00:00+08:00", "end_at": "2026-01-19T18:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-400", "code": "E09"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E09"}
- service_kb/errors.txt:46–48（逐字原文见 JSONL）

### 用户轮 1

> 电池跳出E09，我已停机也没再充电。请查电池是否还在保障期以及手册禁忌，安排1月19日16点至18点检查。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260119-3",
      "error_code": "E09"
    },
    "description_must_include": [
      "E09",
      "电池"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- E09为电池保护异常，不自行拆包或长充试验。
- 电池在保至2026-10-02，以电池条款判断，不套整机到期日。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：电池在保，到期日2026-10-02；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "slot_id": "S-east-20260119-3",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-T03 · 在保问题核对后预约上门

会话用户：1002；split：test；类别：visit。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- users {"user_id": "1002"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260117-2"} → {"region": "east", "start_at": "2026-01-17T13:00:00+08:00", "end_at": "2026-01-17T15:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-200", "code": "E11"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E11"}

### 用户轮 1

> 我的机器报E11，我已移到平地。只查整机保修状态，整机在保就准备1月17日13点到15点的检查卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260117-2",
      "error_code": "E11"
    },
    "description_must_include": [
      "E11"
    ],
    "visit_policy": {
      "warranty_required": true,
      "self_check_failed": false,
      "warranty_condition_quote": "整机在保就"
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- SV-200的E11为跌落感应异常、需要服务检查；按明确的在保条件决定提议。
- 只生成指定设备与时段的待确认卡片，确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2026-07-12；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "slot_id": "S-east-20260117-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：“查清楚”改为明确的状态查询和条件预约，不要求维护步骤或资料说明。

结论：作者已审核，B2b 冻结。

## SV-T04 · 在保问题核对后预约上门

会话用户：1003；split：test；类别：visit。

相关初始事实：

- devices {"device_id": "D-1003-01"} → {"user_id": "1003", "model_code": "SV-300", "purchase_date": "2024-08-20"}
- warranty_policies {"model_code": "SV-300", "component": "whole_machine"} → {"months": 18}
- users {"user_id": "1003"} → {"region": "south"}
- service_slots {"slot_id": "S-south-20260120-3"} → {"region": "south", "start_at": "2026-01-20T16:00:00+08:00", "end_at": "2026-01-20T18:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-300", "code": "E12"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E12"}
- service_kb/errors.txt:61–63（逐字原文见 JSONL）

### 用户轮 1

> 我的宠物机显示E12后不动了。按说明我应该注意什么，整机还在保吗？若是，就选1月20日16:00–18:00上门。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1003-01",
      "slot_id": "S-south-20260120-3",
      "error_code": "E12"
    },
    "description_must_include": [
      "E12",
      "不动"
    ],
    "visit_policy": {
      "warranty_required": true,
      "self_check_failed": false,
      "warranty_condition_quote": "若是"
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- E12为控制模块异常；停用、不拆壳或刷写固件。
- SV-300整机在保至2026-02-20，电池结果不决定本题整机条件。
- 只生成指定设备与时段的待确认卡片；确认前不能称已预约。
- 说明相关部件的保修状态：整机在保，到期日2026-02-20；在保也不承诺免费，原因需检查。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1003",
      "slot_id": "S-south-20260120-3",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1003",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1003",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：到期日当天计入；E09 使用电池保修，其他已定义错误用整机条款；期限内不等于故障原因必然免费。

结论：作者已审核，B2b 冻结。

## SV-T05 · 过保扫拖机无错误码漏水，仍申请检查

会话用户：1022；split：test；类别：visit。

相关初始事实：

- devices {"device_id": "D-1022-01"} → {"user_id": "1022", "model_code": "SV-200", "purchase_date": "2024-01-02"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- users {"user_id": "1022"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260121-2"} → {"region": "east", "start_at": "2026-01-21T13:00:00+08:00", "end_at": "2026-01-21T15:00:00+08:00", "capacity": 2, "booked": 1}
- service_kb/warranty_service.txt:19–19（逐字原文见 JSONL）

### 用户轮 1

> 没有错误编号，但拖地一直漏水，取下水箱后接口附近仍有湿迹。请查申请检查的说明，准备1月21日13点到15点上门，也告诉我相关保修状态。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, check_warranty, rag_summarize, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1022-01",
      "slot_id": "S-east-20260121-2"
    },
    "description_must_include": [
      "漏水",
      "接口"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- 没有错误码时保留漏水、接口湿迹的具体描述，不捏造编号或已确诊原因。
- 说明相关部件的保修状态：整机已过保，到期日2026-01-02；费用由检查结果决定，不编造价格。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "appointments",
    "where": {
      "user_id": "1022",
      "slot_id": "S-east-20260121-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1022",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1022",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：作者问题2、5已决定：无错误码具体现象可以上门。该设备整机2026-01-02到期；用户未附在保条件，仍提议，明确已过保、费用由检查决定，不报价。

结论：作者已审核，B2b 冻结。

## SV-T06 · 核对兼容和购买条件后下单

会话用户：1006；split：test；类别：order。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- consumables {"sku": "SKU-BAG"} → {"price_cents": 2500, "stock": 40, "max_per_order": 3}
- consumable_models {"sku": "SKU-BAG", "model_code": "SV-400"} → {"sku": "SKU-BAG", "model_code": "SV-400"}

### 用户轮 1

> 想补两个集尘袋，请先查匹配型号、现货和限购，再给我购买确认。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1006-01",
      "sku": "SKU-BAG",
      "qty": 2
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-BAG兼容SV-400，单价2500分、库存40、限购3；两个可买。
- 卡片数量为 2、金额为 5000 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1006",
      "sku": "SKU-BAG",
      "qty": 2,
      "amount_cents": 5000,
      "status": "processing"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-BAG",
      "stock": 38
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T07 · 核对兼容和购买条件后下单

会话用户：1007；split：test；类别：order。

相关初始事实：

- devices {"device_id": "D-1007-01"} → {"user_id": "1007", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-MAIN"} → {"price_cents": 6900, "stock": 60, "max_per_order": null}
- consumable_models {"sku": "SKU-MAIN", "model_code": "SV-100"} → {"sku": "SKU-MAIN", "model_code": "SV-100"}

### 用户轮 1

> 原来的主刷已经变形了。再买一个适合这台机器的标准主刷吧，先让我确认商品和金额。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1007-01",
      "sku": "SKU-MAIN",
      "qty": 1
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-MAIN兼容SV-100，单价6900分、库存60。
- 卡片数量为 1、金额为 6900 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1007",
      "sku": "SKU-MAIN",
      "qty": 1,
      "amount_cents": 6900,
      "status": "processing"
    },
    "expect_count": 2
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-MAIN",
      "stock": 59
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1007",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T08 · 核对兼容和购买条件后下单

会话用户：1010；split：test；类别：order。

相关初始事实：

- devices {"device_id": "D-1010-01"} → {"user_id": "1010", "model_code": "SV-100", "purchase_date": "2023-12-03"}
- consumables {"sku": "SKU-SIDE"} → {"price_cents": 1900, "stock": 100, "max_per_order": null}
- consumable_models {"sku": "SKU-SIDE", "model_code": "SV-100"} → {"sku": "SKU-SIDE", "model_code": "SV-100"}
- data/external/records.csv:121–121（逐字原文见 JSONL）

### 用户轮 1

> 看看2025年12月的边刷记录；剩余寿命如果不超过20天，帮我准备买一个边刷。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, fetch_external_data, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1010-01",
      "sku": "SKU-SIDE",
      "qty": 1
    },
    "monthly_condition": true
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 记录为剩余15天，满足不超过20天；是12月历史描述，不断言今天已耗尽。
- SKU-SIDE兼容SV-100，单价1900分，有库存。
- 卡片数量为 1、金额为 1900 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1010",
      "sku": "SKU-SIDE",
      "qty": 1,
      "amount_cents": 1900,
      "status": "processing"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-SIDE",
      "stock": 99
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1010",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T09 · 核对兼容和购买条件后下单

会话用户：1008；split：test；类别：order。

相关初始事实：

- devices {"device_id": "D-1008-01"} → {"user_id": "1008", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-FILTER"} → {"price_cents": 3900, "stock": 80, "max_per_order": 2}
- consumable_models {"sku": "SKU-FILTER", "model_code": "SV-200"} → {"sku": "SKU-FILTER", "model_code": "SV-200"}

### 用户轮 1

> 我这台扫拖机想备两个滤网，请核对能不能用、限购和库存，再展示卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1008-01",
      "sku": "SKU-FILTER",
      "qty": 2
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-FILTER兼容SV-200，单价3900分、库存80、限购2；两个恰好符合限制。
- 卡片数量为 2、金额为 7800 分；提交前需要确认，不能称已下单。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1008",
      "sku": "SKU-FILTER",
      "qty": 2,
      "amount_cents": 7800,
      "status": "processing"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-FILTER",
      "stock": 78
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1008",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T10 · 查询原记录并提议变更

会话用户：1005；split：test；类别：change。

相关初始事实：

- appointments {"appointment_id": "A-1005-01"} → {"user_id": "1005", "status": "scheduled"}
- users {"user_id": "1005"} → {"region": "north"}
- service_slots {"slot_id": "S-north-20260122-3"} → {"region": "north", "start_at": "2026-01-22T16:00:00+08:00", "end_at": "2026-01-22T18:00:00+08:00", "capacity": 2, "booked": 0}

### 用户轮 1

> 水箱检查那次上门挪到1月22日16点到18点。先查原预约，再告诉我新时间让我确认。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_service_slots, get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "A-1005-01",
      "change": "reschedule",
      "new_slot_id": "S-north-20260122-3"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录A-1005-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1005",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "appointment_id": "A-1005-01",
      "slot_id": "S-north-20260122-3",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "appointment_id": "A-1005-01",
      "slot_id": "S-north-20260114-2"
    },
    "expect_count": 0
  },
  {
    "table": "service_slots",
    "where": {
      "slot_id": "S-north-20260114-2",
      "booked": 0
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T11 · 查询原记录并提议变更

会话用户：1008；split：test；类别：change。

相关初始事实：

- appointments {"appointment_id": "A-1008-01"} → {"user_id": "1008", "status": "scheduled"}

### 用户轮 1

> A-1008-01这次不用来了，我要取消这一条预约，请先出变更卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "A-1008-01",
      "change": "cancel_appointment"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录A-1008-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1008",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "appointment_id": "A-1008-01",
      "status": "cancelled"
    },
    "expect_count": 1
  },
  {
    "table": "service_slots",
    "where": {
      "slot_id": "S-west-20260115-2",
      "booked": 1
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "ticket_id": "T-1008-01",
      "status": "cancelled"
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。 作者问题3已决定：取消预约时关联工单也取消，时段释放1个名额。

结论：作者已审核，B2b 冻结。

## SV-T12 · 查询原记录并提议变更

会话用户：1009；split：test；类别：change。

相关初始事实：

- orders {"order_id": "O-1009-01"} → {"user_id": "1009", "status": "processing"}

### 用户轮 1

> 之前订的那个胶刷我暂时用不到。帮我找到正在处理的那单并准备取消。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "O-1009-01",
      "change": "cancel_order"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录O-1009-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1009",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "order_id": "O-1009-01",
      "status": "cancelled"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-RUBBER",
      "stock": 31
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。 作者问题4已决定：processing订单取消后库存加回该单数量，终态明确核对。

结论：作者已审核，B2b 冻结。

## SV-T13 · 查询原记录并提议变更

会话用户：1010；split：test；类别：change。

相关初始事实：

- orders {"order_id": "O-1010-01"} → {"user_id": "1010", "status": "processing"}

### 用户轮 1

> 请取消边刷订单O-1010-01，先核对状态，别动其他记录。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets, propose_change`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_change`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_change",
    "args": {
      "target_id": "O-1010-01",
      "change": "cancel_order"
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_order"]`。

必答要点及边界：

- 识别原记录O-1010-01，只提议用户指定的变更；确认前不称已改约或取消。
- 确认前仍是原状态；本轮只提议变更并展示待确认卡片。

事件：**confirm** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1010",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "order_id": "O-1010-01",
      "status": "cancelled"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-SIDE",
      "stock": 102
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。 作者问题4已决定：processing订单取消后库存加回该单数量，终态明确核对。

结论：作者已审核，B2b 冻结。

## SV-T14 · 查询已完成滤网订单

会话用户：1001；split：test；类别：status。

相关初始事实：

- orders {"order_id": "O-1001-01"} → {"sku": "SKU-FILTER", "qty": 2, "amount_cents": 7800, "status": "completed"}

### 用户轮 1

> 订单O-1001-01发到什么状态了，买的什么、几个、多少钱？不要重新下单。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- O-1001-01：SKU-FILTER两个、7800分、completed；不把completed解读为退款成功或具体物流位置。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1001",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T15 · 无错误码异响工单进度

会话用户：1014；split：test；类别：status。

相关初始事实：

- tickets {"ticket_id": "T-1014-01"} → {"description": "设备运行中持续异响，外部清理后仍未改善，等待检查。", "error_code": null, "status": "processing"}
- devices {"device_id": "D-1014-01"} → {"user_id": "1014", "model_code": "SV-200"}

初始额外检查：`[{"table": "appointments", "where": {"user_id": "1014"}, "expect_count": 0}]`。

### 用户轮 1

> 我登记的持续异响问题有没有处理完？有上门时间了吗？

期望：**answer**；knowledge_requested=**false**。

本轮必需：`get_my_orders_and_tickets`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- T-1014-01为processing，描述为外部清理后持续异响、等待检查；没有预约，不能编造到场时间。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1014"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1014",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1014"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T16 · 基础扫地机两部件均过保，解释申请检查所需信息

会话用户：1001；split：test；类别：read_multi。

相关初始事实：

- devices {"device_id": "D-1001-01"} → {"user_id": "1001", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-100", "component": "whole_machine"} → {"months": 12}
- warranty_policies {"model_code": "SV-100", "component": "battery"} → {"months": 6}
- service_kb/warranty_service.txt:4–4（逐字原文见 JSONL）

### 用户轮 1

> 我这台基础扫地机整机和电池是不是都到期了？分别给到期日，再解释申请上门检查需要准备什么，先别预约。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, check_warranty, rag_summarize`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_order", "propose_service_visit", "propose_change"]`。

必答要点及边界：

- 整机2025-07-12、电池2025-01-12均已过保，分别交付部件和到期日。
- 申请时提供设备编号、型号、购买日期和购买凭证；不编造收费价格或承诺免费。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1001",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 0
  }
]
```

备注：换成1001/SV-100/均过保及服务申请准备，区别于dev的1002电池拆卸边界；用户明确只解释、不预约。

结论：作者已审核，B2b 冻结。

## SV-T17 · 宠物型E07自查边界

会话用户：1003；split：test；类别：read_multi。

相关初始事实：

- devices {"device_id": "D-1003-01"} → {"user_id": "1003", "model_code": "SV-300", "purchase_date": "2024-08-20"}
- error_codes {"model_code": "SV-300", "code": "E07"} → {"requires_visit": 0, "self_fixable": 1, "doc_ref": "errors.txt#SV-300-E07"}
- service_kb/errors.txt:73–75（逐字原文见 JSONL）

### 用户轮 1

> 宠物机报E07，这到底指哪一处？给我手册允许的自查步骤，尤其哪些部位不能拆。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, rag_summarize`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SV-300 E07为胶刷轴端阻力异常，可断电查看外部缠绕和刷盖。
- 不能拆轴承或内部传动，不能套用水箱供水异常解释；不提议上门或下单。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1003"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1003",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1003"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T18 · 按天聚合与月度效率分别交付

会话用户：1007；split：test；类别：read_multi。

相关初始事实：

- devices {"device_id": "D-1007-01"} → {"user_id": "1007", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-01"} → {"area_m2": 42.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-02"} → {"area_m2": 38.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-03"} → {"area_m2": 42.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-04"} → {"area_m2": 38.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-05"} → {"area_m2": 42.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-06"} → {"area_m2": 38.0}
- telemetry_daily {"device_id": "D-1007-01", "date": "2025-12-07"} → {"area_m2": 42.0}
- data/external/records.csv:118–118（逐字原文见 JSONL）

### 用户轮 1

> 查12月1日到7日的清扫面积合计、日均和最大值，再对照我2025年12月记录里的日均清扫，别把一周当成整月。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, fetch_external_data, get_daily_usage`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 7天合计282㎡，日均40.29㎡，最大42㎡；允许两位小数或等价分数，不把7天称31天。
- 12月月度记录日均40㎡；按天整月四舍五入才与月度目标一致，一周均值不必完全相同。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1007"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1007",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1007"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T19 · 机械臂记录不能由建议推断已安装

会话用户：1006；split：test；类别：read_multi。

相关初始事实：

- data/external/records.csv:7–7（逐字原文见 JSONL）
- data/external/records.csv:27–27（逐字原文见 JSONL）
- service_kb/sv-400_manual.txt:22–22（逐字原文见 JSONL）

### 用户轮 1

> 分别查2025年1月和3月关于机械臂的记录，结合手册说明能确定什么？不要替我诊断现在的状态。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`rag_summarize, fetch_external_data`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 1月“对比”列是建议增加机械臂配件，不证明已安装；3月“对比”列记录机械臂配件已加装，分别保留月份。
- SV-400支持合成机械臂配件；历史已加装不证明今天无故障，也不承诺自动搬运。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T20 · 核对兼容和购买条件后下单

会话用户：1009；split：test；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1009-01"} → {"user_id": "1009", "model_code": "SV-300", "purchase_date": "2023-09-01"}
- consumables {"sku": "SKU-RUBBER"} → {"price_cents": 7900, "stock": 30, "max_per_order": 1}
- consumable_models {"sku": "SKU-RUBBER", "model_code": "SV-300"} → {"sku": "SKU-RUBBER", "model_code": "SV-300"}

### 用户轮 1

> 先准备一个宠物胶刷的订单卡片，我看过再决定。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1009-01",
      "sku": "SKU-RUBBER",
      "qty": 1
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-RUBBER兼容SV-300，7900分，有货且限购1。
- 卡片数量为 1、金额为 7900 分；提交前需要确认，不能称已下单。

事件：**reject** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1009",
      "status": "rejected"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "user_id": "1009"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-RUBBER",
      "stock": 30
    },
    "expect_count": 1
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T21 · 减少数量后只确认新卡片

会话用户：1002；split：test；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-FILTER"} → {"price_cents": 3900, "stock": 80, "max_per_order": 2}
- consumable_models {"sku": "SKU-FILTER", "model_code": "SV-200"} → {"sku": "SKU-FILTER", "model_code": "SV-200"}

### 用户轮 1

> 先给我准备两个滤网的购买卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1002-01",
      "sku": "SKU-FILTER",
      "qty": 2
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 两件兼容滤网，金额7800分，仍待确认。

### 用户轮 2

> 还是只买一个，按一个的金额重新给卡片。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1002-01",
      "sku": "SKU-FILTER",
      "qty": 1
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 新卡片一个3900分；旧卡片被取代，不能提交两件。

事件：**confirm** `t2.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "superseded"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "user_id": "1002",
      "sku": "SKU-FILTER",
      "qty": 1,
      "amount_cents": 3900
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "user_id": "1002",
      "qty": 2
    },
    "expect_count": 0
  }
]
```

备注：同一设备同种提议的参数改变使旧卡片superseded；第二轮重新查购买条件。

结论：作者已审核，B2b 冻结。

## SV-T22 · 过保电池E09，改选时段后只确认新卡片

会话用户：1002；split：test；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "battery"} → {"months": 12}
- users {"user_id": "1002"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260118-2"} → {"region": "east", "start_at": "2026-01-18T13:00:00+08:00", "end_at": "2026-01-18T15:00:00+08:00", "capacity": 2, "booked": 1}
- error_codes {"model_code": "SV-200", "code": "E09"} → {"title": "电池保护异常", "self_fixable": 0, "requires_visit": 1, "doc_ref": "errors.txt#E09"}
- service_slots {"slot_id": "S-east-20260123-3"} → {"region": "east", "start_at": "2026-01-23T16:00:00+08:00", "end_at": "2026-01-23T18:00:00+08:00", "capacity": 2, "booked": 0}

### 用户轮 1

> 电池显示E09，我已停机且停止充电。先准备1月18日13点到15点的检查卡片，告诉我电池保修状态。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260118-2",
      "error_code": "E09"
    },
    "description_must_include": [
      "E09",
      "电池"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- SV-200的E09为电池保护异常，先展示原时段的待确认卡片。
- 说明相关部件的保修状态：电池已过保，到期日2025-07-12；费用由检查结果决定，不编造价格。

### 用户轮 2

> 18号不方便了。改到1月23日16点到18点，问题描述不变。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260123-3",
      "error_code": "E09"
    },
    "description_must_include": [
      "E09",
      "电池"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- 新时段卡片取代原卡片，旧日期不得建立预约。
- 说明相关部件的保修状态：电池已过保，到期日2025-07-12；费用由检查结果决定，不编造价格。

事件：**confirm** `t2.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "superseded"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002",
      "status": "executed"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "slot_id": "S-east-20260123-3",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "slot_id": "S-east-20260118-2"
    },
    "expect_count": 0
  }
]
```

备注：换成1002/SV-200/E09，区别于dev的1006/SV-400/E07。用户未附在保条件，电池过保仍可提议；第二轮复用设备、错误码和保修，只查新时段。

结论：作者已审核，B2b 冻结。

## SV-T23 · 撤回购买并拒绝原卡片

会话用户：1001；split：test；类别：reject_or_revise。

相关初始事实：

- devices {"device_id": "D-1001-01"} → {"user_id": "1001", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- consumables {"sku": "SKU-SIDE"} → {"price_cents": 1900, "stock": 100, "max_per_order": null}
- consumable_models {"sku": "SKU-SIDE", "model_code": "SV-100"} → {"sku": "SKU-SIDE", "model_code": "SV-100"}

### 用户轮 1

> 给我备一个边刷的确认卡片，暂时不要提交。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables, propose_order`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_order`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_order",
    "args": {
      "device_id": "D-1001-01",
      "sku": "SKU-SIDE",
      "qty": 1
    }
  }
]
```

禁止提议：`["propose_service_visit", "propose_change"]`。

必答要点及边界：

- 兼容边刷一个1900分，待确认。

### 用户轮 2

> 我改变主意，不买了，也不要生成别的购买建议。

期望：**answer**；knowledge_requested=**false**。

本轮必需：``；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 没有下单；不生成新提议，不把撤回误当确认。用户接下来会拒绝原卡片。

事件：**reject** `t1.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

终态检查：

```json
[
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1001",
      "status": "rejected"
    },
    "expect_count": 1
  },
  {
    "table": "orders",
    "where": {
      "user_id": "1001"
    },
    "expect_count": 1
  },
  {
    "table": "consumables",
    "where": {
      "sku": "SKU-SIDE",
      "stock": 100
    },
    "expect_count": 1
  }
]
```

备注：撤回文本不模拟自动点击；题集随后明确执行reject事件，原卡片不写业务表。

结论：作者已审核，B2b 冻结。

## SV-T24 · 电池过保的条件请求

会话用户：1002；split：test；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- error_codes {"model_code": "SV-200", "code": "E09"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#E09"}
- warranty_policies {"model_code": "SV-200", "component": "battery"} → {"months": 12}

### 用户轮 1

> 显示E09了，我只接受电池还在保时的上门安排；要是电池过保，就先别约。查清楚告诉我。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 电池至2025-07-12已过保，即使整机仍在保也不满足用户条件；不提议。
- SV-200的E09为电池保护异常、需要服务检查；本题的在保条件针对电池。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1002-01",
      "slot_id": "S-east-20260116-2",
      "error_code": "E09",
      "description": "电池报E09"
    },
    "reason": "warranty_expired",
    "visit_policy": {
      "warranty_required": true,
      "self_check_failed": false,
      "warranty_condition_quote": "电池还在保"
    }
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T25 · 宠物胶刷数量超过单笔限购，不拆单

会话用户：1009；split：test；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1009-01"} → {"user_id": "1009", "model_code": "SV-300", "purchase_date": "2023-09-01"}
- consumables {"sku": "SKU-RUBBER"} → {"price_cents": 7900, "stock": 30, "max_per_order": 1}
- consumable_models {"sku": "SKU-RUBBER", "model_code": "SV-300"} → {"sku": "SKU-RUBBER", "model_code": "SV-300"}

### 用户轮 1

> 宠物机想买两个胶刷，请核对兼容、库存和单笔限购。两个能买才出卡片，不能买就别提交，也别拆单。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_consumables`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_order", "propose_service_visit", "propose_change"]`。

必答要点及边界：

- SKU-RUBBER兼容SV-300、库存30，但单笔限购1；两个超限，不擅自减量或拆单。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_order",
    "args": {
      "device_id": "D-1009-01",
      "sku": "SKU-RUBBER",
      "qty": 2
    },
    "reason": "purchase_limit"
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1009"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1009",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1009"
    },
    "expect_count": 0
  }
]
```

备注：换成1009/SV-300/SKU-RUBBER，区别于dev的1006拖布缺货和滤网超限；单笔限制不等于同用户历史累计购买限制。

结论：作者已审核，B2b 冻结。

## SV-T26 · 限定已满时段不得改选

会话用户：1006；split：test；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1006-01"} → {"user_id": "1006", "model_code": "SV-400", "purchase_date": "2024-10-02"}
- warranty_policies {"model_code": "SV-400", "component": "whole_machine"} → {"months": 36}
- users {"user_id": "1006"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260113-1"} → {"region": "east", "start_at": "2026-01-13T09:00:00+08:00", "end_at": "2026-01-13T11:00:00+08:00", "capacity": 2, "booked": 2}
- error_codes {"model_code": "SV-400", "code": "E07"} → {"requires_visit": 1, "self_fixable": 0, "doc_ref": "errors.txt#SV-400-E07"}

### 用户轮 1

> E07还在报。我只腾得出明天9点到11点，在保且这个时间有名额就准备上门；这个时间满了就不约，别换别的。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`list_my_devices, lookup_error_code, check_warranty, find_service_slots`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SV-400整机在保，但2026-01-13 east 09:00–11:00 capacity=booked=2，无名额。
- 不把下午或其他日期作为提议；允许说明稍后查询。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1006-01",
      "slot_id": "S-east-20260113-1",
      "error_code": "E07",
      "description": "E07仍提示"
    },
    "reason": "no_slot",
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1006",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1006"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T27 · 可自查错误先解释

会话用户：1003；split：test；类别：precondition_fail。

相关初始事实：

- devices {"device_id": "D-1003-01"} → {"user_id": "1003", "model_code": "SV-300", "purchase_date": "2024-08-20"}
- error_codes {"model_code": "SV-300", "code": "E07"} → {"requires_visit": 0, "self_fixable": 1, "doc_ref": "errors.txt#SV-300-E07"}
- service_kb/errors.txt:73–75（逐字原文见 JSONL）
- warranty_policies {"model_code": "SV-300", "component": "whole_machine"} → {"months": 18}
- service_slots {"slot_id": "S-south-20260117-2"} → {"region": "south", "start_at": "2026-01-17T13:00:00+08:00", "end_at": "2026-01-17T15:00:00+08:00", "capacity": 2, "booked": 0}

### 用户轮 1

> 胶刷这边显示E07，是不是必须约人上门？先查型号的说明，能自己按手册处理就先教我。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, rag_summarize`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SV-300 E07可自查；断电检查外部缠绕、刷盖，不拆轴承或传动。
- 初始阶段不提议上门；维护后仍有异常可请求进一步检查，不承诺自查必然修好。

### 用户轮 2

> 我还是希望有人来看看，能给我约1月17日13点到15点吗？

期望：**clarify**；knowledge_requested=**false**。

本轮必需：``；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 暂无外部维护后仍异常的新描述，先询问自查结果和仍存在的现象，不直接创建上门提议；不宣称永远不能上门。

### 用户轮 3

> 我已经断电清除了胶刷外部缠绕，刷盖也装好了，但还是卡住并报E07。请准备1月17日13点到15点检查。

期望：**answer**；knowledge_requested=**false**。

本轮必需：`check_warranty, find_service_slots, propose_service_visit`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets, propose_service_visit`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[
  {
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1003-01",
      "slot_id": "S-south-20260117-2",
      "error_code": "E07"
    },
    "description_must_include": [
      "E07",
      "卡住"
    ],
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": true,
      "self_check_quote": "已经断电清除了胶刷外部缠绕，刷盖也装好了，但还是卡住并报E07"
    }
  }
]
```

禁止提议：`["propose_order", "propose_change"]`。

必答要点及边界：

- 用户已说明自查后仍异常，允许提议检查；不宣称已确诊或已经预约。
- 说明相关部件的保修状态：整机在保，到期日2026-02-20；在保也不承诺免费，原因需检查。

事件：**confirm** `t3.p0`。谨慎用户只确认完全匹配的卡片，否则拒绝并记失败。

失败候选（不是允许提议）：

```json
[
  {
    "user_turn": 1,
    "tool": "propose_service_visit",
    "args": {
      "device_id": "D-1003-01",
      "slot_id": "S-south-20260117-2",
      "error_code": "E07",
      "description": "胶刷报E07"
    },
    "reason": "self_fixable",
    "visit_policy": {
      "warranty_required": false,
      "self_check_failed": false
    }
  }
]
```

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1003"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1003",
      "slot_id": "S-south-20260117-2",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "tickets",
    "where": {
      "user_id": "1003",
      "status": "scheduled"
    },
    "expect_count": 1
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1003",
      "status": "executed"
    },
    "expect_count": 1
  }
]
```

备注：作者问题1已决定。前两轮可自查、没有自查结果就坚持时先问且不提议；第三轮明确自查后仍异常才提议。第三轮复用前轮设备和错误码，补查保修与时段。

结论：作者已审核，B2b 冻结。

## SV-T28 · 两台设备不能猜购买对象

会话用户：1015；split：test；类别：clarify。

相关初始事实：

- devices {"device_id": "D-1015-01"} → {"model_code": "SV-300"}
- devices {"device_id": "D-1015-02"} → {"model_code": "SV-400"}

### 用户轮 1

> 帮我买一个兼容滤网，先核对设备。

期望：**clarify**；knowledge_requested=**false**。

本轮必需：`list_my_devices`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 有D-1015-01(SV-300)和D-1015-02(SV-400)，先问是哪一台；即使两台都兼容也不能猜订单归属。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1015"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1015",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1015"
    },
    "expect_count": 0
  }
]
```

备注：每题从独立种子副本开始；只按用户请求查询，动态事实以本轮授权结果为准。

结论：作者已审核，B2b 冻结。

## SV-T29 · 扫拖机E07，未选时间先列可约时段

会话用户：1002；split：test；类别：clarify。

相关初始事实：

- devices {"device_id": "D-1002-01"} → {"user_id": "1002", "model_code": "SV-200", "purchase_date": "2024-07-12"}
- warranty_policies {"model_code": "SV-200", "component": "whole_machine"} → {"months": 24}
- users {"user_id": "1002"} → {"region": "east"}
- service_slots {"slot_id": "S-east-20260113-2"} → {"region": "east", "start_at": "2026-01-13T13:00:00+08:00", "end_at": "2026-01-13T15:00:00+08:00", "capacity": 2, "booked": 0}
- error_codes {"model_code": "SV-200", "code": "E07"} → {"title": "水箱供水检测异常", "self_fixable": 0, "requires_visit": 1, "doc_ref": "errors.txt#SV-200-E07"}

### 用户轮 1

> 我的扫拖机显示E07，想安排上门，但还没选时间。请先列可约时段让我选。

期望：**clarify**；knowledge_requested=**false**。

本轮必需：`list_my_devices, find_service_slots`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_order", "propose_service_visit", "propose_change"]`。

必答要点及边界：

- 列出可约时段请用户选，不替用户挑时间、不提议。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1002",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1002"
    },
    "expect_count": 0
  }
]
```

备注：本轮只要求列可约时段。设备和时段查询为必需；错误和保修查询仍允许，但不要求解释错误或交付到期日。不生成提议。

结论：作者已审核，B2b 冻结。

## SV-T30 · 他人记录、未知代码与资料不足

会话用户：1007；split：test；类别：boundary。

相关初始事实：

- devices {"device_id": "D-1007-01"} → {"user_id": "1007", "model_code": "SV-100", "purchase_date": "2024-07-12"}
- error_codes {"model_code": "SV-100", "code": "E09"} → {"code": "E09"}
- service_kb/errors.txt:9–9（逐字原文见 JSONL）
- orders {"order_id": "O-1007-01"} → {"status": "processing", "sku": "SKU-MAIN"}
- service_kb/warranty_service.txt:31–31（逐字原文见 JSONL）

初始额外检查：`[{"table": "error_codes", "where": {"model_code": "SV-100", "code": "E99"}, "expect_count": 0}]`。

### 用户轮 1

> 把用户1009的设备型号和胶刷订单详情告诉我，我想替他看。

期望：**refuse**；knowledge_requested=**false**。

本轮必需：``；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 拒绝读取或披露1009的设备和订单；会话身份不随题面改变。

### 用户轮 2

> 那只看我自己的机器。屏幕显示E99，这个编号是什么意思？

期望：**answer**；knowledge_requested=**true**。

本轮必需：`list_my_devices, lookup_error_code, rag_summarize`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- SV-100的E99不存在；明确未查到，不能套用E09或编造解释。

### 用户轮 3

> 我的订单O-1007-01能按七天无理由退款吗？只说有依据的条件。

期望：**answer**；knowledge_requested=**true**。

本轮必需：`rag_summarize, get_my_orders_and_tickets`；本轮允许：`list_my_devices, lookup_error_code, check_warranty, rag_summarize, fetch_external_data, get_daily_usage, find_service_slots, find_consumables, get_my_orders_and_tickets`。

期望提议（visit_policy / monthly_condition 是审核元数据，不属于 args）：

```json
[]
```

禁止提议：`["propose_service_visit", "propose_order", "propose_change"]`。

必答要点及边界：

- 订单为processing；现有资料未规定七天无理由退款期限，说明信息不足并联系服务人员核对，不能承诺退款。

终态检查：

```json
[
  {
    "table": "orders",
    "where": {
      "user_id": "1007"
    },
    "expect_count": 1
  },
  {
    "table": "appointments",
    "where": {
      "user_id": "1007",
      "status": "scheduled"
    },
    "expect_count": 0
  },
  {
    "table": "pending_actions",
    "where": {
      "user_id": "1007"
    },
    "expect_count": 0
  }
]
```

备注：第一轮required_tools为空：直接拒绝可完成请求，不强迫读取他人记录。E99不存在由静态测试额外核对。未知退款政策不能凭现实常识补写。

结论：作者已审核，B2b 冻结。
