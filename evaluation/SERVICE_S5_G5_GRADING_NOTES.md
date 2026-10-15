# S5 G5 已见回归盲评记录

评审方：Claude（助手），2026-10-16。属于“助手辅助、隐藏标签”的盲评，不是独立专家评审。

范围：三个已见集合，每个集合把 legacy + react 和 service + react 两种组合的结果混在一起打乱。评分时没有打开 `blind_key.jsonl`，也没有打开同目录下的 `comparison.json` 和 `comparison.md`。

## 锁定

| 集合 | 样本 | 盲评 task_pass | blind_scores.jsonl 的 SHA256 | blind_scores_lock.json 的 SHA256 |
|---|---:|---:|---|---|
| base（A01–A12） | 24 | 15 | `ba8ac6b891f9c64d54da6afc534cd27ece70c1eadfd6a110e168c75ca84a3025` | `3b9b7406802e819c7df4f28a840a95b926f7c3850dd8ccbb6e8d0e5bb4f6d649` |
| generalization_v1 | 12 | 6 | `60eb11a84c1809cd22eff146d95e9a13743f4cdaecdbfef8059b67f0f12e56d7` | `8518306f6daff1b43b1df64845804111b5f998098c36381434126431a13be76b` |
| holdout_v2 | 12 | 6 | `26d82032b1fc10e9713a8de4cce8627fcba0f82b5c8099a39c2e9a81fdbdfb71` | `feab0ec5120288c5afa83b5c3a7a02ecfdd09f2c3524b3cc60b8a2168d2cf159` |

- 每条评分含 sample_id、案例号、逐轮内容分（answer_score）和忠实度（grounded）、整体 task_pass，以及理由。
- 锁文件记录 blind_cases、blind_key（取自 manifest）和 blind_manifest 的哈希。
- result_sha256 在揭盲时从 blind_key 补入。

## 口径

依据各集合自己的 SCORING：`evaluation/generalization_v1/SCORING.md`、`evaluation/holdout_v2/SCORING.md`、`evaluation/SEMANTIC_REVIEW_V2.md`，以及 `evaluation/cases.md` 的 A 题判分说明。

1. **task_pass 的条件：** 每个计划轮次内容 2、忠实度为真，且执行完成。工具选择按各集合规则单独报告，不并入 task_pass。未执行的轮次记 0 分、不忠实，留在分母。
2. **“只列 / 只回答 / 只需要”：** 用户明确限定字段，回答却列出整份月报或其他字段，内容记 1。
3. **身份缺失、非法月份、跨用户请求：** 只回复通用的“工具调用未通过安全检查，请检查会话设置后重试”、没有说明具体原因的，内容记 1。
4. **自相矛盾的开头：** 开头称“本次查询未完成…请重试”，后面又给出正确内容的，内容记 1。
5. **“本月”的口径：** 冻结题 A05 的“本月”是执行月 2026-10。按业务日期口径改查 2026-01 的，判为月份不符，内容记 1。
6. **检索总结也算回答：** 逐条对照实际送入模型的资料。以下情况判为不忠实：
   - 编造手册出处，例如把维护保养第 20 条说成“设备手册（SV-100）第20条”；
   - 套用其他部件的周期；
   - 资料中没有的设备状态，例如“当前滤网状态正常”。

## 需在报告中披露

- **工具轨迹会暴露工具集。** 例如 list_my_devices、get_daily_usage、device_id 参数，以及 2026-01 业务日期，都能看出是哪种工具集，所以只是隐藏标签，并非真正不可辨识。
- **盲评目录里放了揭盲线索。** 评审方没有打开这两个文件，但今后生成盲评包时应把它们与盲评包分开存放。
  - comparison.json/md 带有按案例的前后结果哈希和状态。
  - blind_key.jsonl 也在同一目录。
- **holdout_v2/legacy 曾因外部进程终止重跑。** 用户已授权，原故障目录保留。
- **holdout_v2/service 的 V2A05 超时。** 返回 DeadlineExceeded，保留在分母中。

## 评分中观察到的问题（揭盲后再归属组合）

- **把整份报告当回答：** 用户只要两三项，模型也输出整份月报，有时还加上无依据的“保养建议”。
- **用错数据源：** 改用逐日遥测 get_daily_usage 代替月度记录，于是说“工具未提供覆盖率 / 未找到字段”。
- **长历史回忆失败：** 在合成长历史后，不回忆目标部件，转去检索资料。
- **多余的调用和失败的参数：** 多调用设备与耗材工具，设备号参数无效（device_1001、device_123）导致失败，回答开头因此出现“查询未完成”。
- **检索失败时凭常识作答：** 检索服务故障时，模型自己给出排查步骤。
