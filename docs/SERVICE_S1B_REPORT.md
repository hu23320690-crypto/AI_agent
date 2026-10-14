# S1-B：service独立索引与型号过滤检索

基于PR #7合并后的main 90964713a92d5bf9a041fbb0fba97dc9403aa64d，分支feat/service-agent-s1b。本阶段不读取service test、注入集或两份GOLD_REVIEW。没有修改冻结输入、已有测试、data、旧清单或现有配置键。真实索引和冒烟仅调用qwen3-embedding:4b，不调用聊天模型。

## 配置和治理

service_rag.yml使用service_kb资料根目录、独立service_knowledge_sources.json、service_chunks_qwen3_governed_v1 collection；persist_directory沿用rag/chroma_db。chunk_size=200、chunk_overlap=20、k=5、candidate_k=20、hybrid、RRF常数60及分隔符与legacy完全一致。

ServiceSourceCatalog复用SourceCatalog审批、未审批隔离、撤销和风险规则，并要求审批SHA256匹配冻结service_kb/manifest.json。7份资料已批准，理由均为“S0 作者审核通过的合成资料（PR #5）”。新增来源扫描可隔离，但不能绕过冻结manifest擅自批准。

每个分块保留source、source_id、source_sha256、chunk_id等治理元数据，并新增source_file、knowledge_catalog=service、manifest_sha256和JSON字符串models。Chroma仅支持标量元数据，型号列表用规范化JSON字符串保存；检索时再与manifest逐字核对，不相信索引中自行更换的标签。

管理命令支持catalog选项在子命令前后出现：

```powershell
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge --catalog service scan
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge --catalog service status
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge --catalog service approve sv-300_manual.txt --sha256 <manifest哈希> --reason "S0 作者审核通过的合成资料（PR #5）"
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge --catalog service revoke <source_id> --reason <撤销原因>
.\.venv\Scripts\python.exe -B scripts/manage.py knowledge --catalog service sync
```

doctor新增清单解析及已审批SHA256与manifest匹配两个检查。不要求doctor连接Ollama或存在本地索引。

## 型号过滤与融合

服务工具先在同一只读数据库连接中检查设备归属，再确定型号：明确device_id使用该设备；省略但仅有一台设备使用该台；多台或没有设备时型号为None，仅取all。型号不由模型参数、题面或历史摘要决定。

service检索先执行来源治理，再按经过manifest验证的models筛选eligible分块。只有筛选后的chunk_id进入Chroma dense过滤，BM25/覆盖度重排的语料也是同一eligible集合；其他型号不会占用候选窗口。legacy资料在service视图中标为all。

两个collection各取最多20个hybrid候选，使用现有fuse进行RRF(k=60)，随后按catalog+source_id执行单来源配额3、近重复阈值0.96和Top-5。catalog命名空间防止相同文件名产生相同source_id后互相占配额。旧legacy检索实现与默认调用参数保持不变。

生成复用原RagSummarizeService的来源验证、输入预算、抽取/生成与EvidenceCheck提交验证。每次service调用使用独立的绑定型号视图，提交前校验不依赖已经退出的ContextVar。references按实际送入回答过程的分块填写来源文件#chunk_id及models，预算剪裁掉的分块不计引用；提交阶段逐块复核不会覆盖已捕获引用集合。

service运行时不会自动同步任何collection。legacy collection以create_collection_if_not_exists=False只读打开；不存在时保持不存在，不能因为service请求创建或重建它。索引变更只由管理员sync执行。

## 离线验证与legacy等价

| 检查 | 修改前 | 修改后 |
| --- | ---: | ---: |
| 完整pytest | 1524 passed | 1558 passed |
| 子测试 | 291 passed | 291 passed |
| 本机符号链接权限跳过 | 3 | 3 |
| 默认doctor --offline | 153/153 | 155/155 |
| service doctor --offline | 153/153 | 155/155 |

完整回归耗时105.12秒，34项新增测试全部通过；已有测试文件一个未改。覆盖审批/标签/CLI/doctor反例、型号与多设备、他人设备拒绝、未审批/篡改/撤销/风险、排名期间/生成后/提交前撤销、实际引用和预算剪裁、来源配额/去重、legacy参数/字节与默认factory、缺失legacy索引不创建。

| 缓存 | 查询数 | 方案数 | Top-5比较数 | 不一致 |
| --- | ---: | ---: | ---: | ---: |
| runtime_stage4_retrieval_dev | 49 | 3 | 147 | 0 |
| runtime_stage4_retrieval_holdout | 12 | 3 | 36 | 0 |
| 合计 | 61 | 3 | 183 | 0 |

回放使用已提交candidate_cache及ablation.json，不调用模型，不重建索引，不宣称缓存代表当前资料授权。原vector_store.py、hybrid.py、security.py、rag_service.py、relevance.py与两个legacy配置均与main基线字节哈希一致。

本机legacy collection仍为agent_chunks_qwen3_governed_v1，326分块。文本+元数据+向量指纹在service建索引和检索前后相同：ec7cc9b03d13fe80fdbe70789a39de15ec9f171301e57147028fbc5a846357d2。

冻结修订01后的contracts.py保持原样；hash-only冻结检查26/26通过。冻结资料和原清单没有变化。

## 真实索引和冒烟

Ollama已安装qwen3-embedding:4b，真实service collection建立成功，7来源、102分块，failed=0、quarantined=0。索引保存在忽略的本地rag/chroma_db，不提交数据库。

| 资料 | 分块数 | 型号标签 |
| --- | ---: | --- |
| consumables.txt | 14 | all |
| errors.txt | 20 | all |
| sv-100_manual.txt | 13 | SV-100 |
| sv-200_manual.txt | 13 | SV-200 |
| sv-300_manual.txt | 14 | SV-300 |
| sv-400_manual.txt | 15 | SV-400 |
| warranty_service.txt | 13 | all |

直接标签分布：SV-100=13、SV-200=13、SV-300=14、SV-400=15、all=47。包含通用分块的可检索数量分别为60、60、61、62；不明确型号时47。

### 宠物家庭的胶刷外侧有毛发缠绕，断电后怎样清理并检查刷盖？

可信型号筛选：SV-300。

| Rank | catalog | 来源 | models | chunk_id |
| --- | --- | --- | --- | --- |
| 1 | legacy | data/扫地机器人100问.pdf | all | b6ed34b06890686f3229526d8fdab14849746a69e62a688cc74d2ae94dc7b658 |
| 2 | service | service_kb/sv-300_manual.txt | SV-300 | 897d4d2f9a1830bbe95318c4d3d95795822ec60c44912d65f86725b56cf951c2 |
| 3 | legacy | data/故障排除.txt | all | c3fafab5c10e8458c3586dcd5f4753b4d967358ec63a3155af21a0ddcb739e6d |
| 4 | service | service_kb/sv-300_manual.txt | SV-300 | 313eb36b00a6fc1a6577cf52ab01d8cec8e32436a0576a092a5f893251c417de |
| 5 | legacy | data/扫地机器人100问2.txt | all | 319a99aeb0ee1201f886fb3f30c81b7c0c3fc2be1c399bab67351fdc15ed8c7d |

### 扫拖机水箱装回后接口仍有湿迹，应该检查哪些外部位置？

可信型号筛选：SV-200。

| Rank | catalog | 来源 | models | chunk_id |
| --- | --- | --- | --- | --- |
| 1 | legacy | data/故障排除.txt | all | 4b92b88a20d7498836bed3a1a7da11c3506eaed157f27a89f65e9b5ecd44b7b1 |
| 2 | service | service_kb/sv-200_manual.txt | SV-200 | d99bc00efb8ae8d1ee235f8a6a0f8e3bb9f3066b544bbb636578eba765a20226 |
| 3 | legacy | data/维护保养.txt | all | 016c09b4586920836bc4768afdaeaa91133369dad7ff2fa3f826ec51ba711067 |
| 4 | service | service_kb/sv-200_manual.txt | SV-200 | 6bcffb644c842a24095be88ef8c65eb01536429fb08be7d026d0c74040ef1b24 |
| 5 | legacy | data/故障排除.txt | all | 7302f2aec24aa72ecd5c1067e6bdd534f8fe3e0da2d442fc4dedeadd273e3340 |

### 家里两台不同型号的设备，报修前通用的准备工作有哪些？

可信型号筛选：None（仅all）。

| Rank | catalog | 来源 | models | chunk_id |
| --- | --- | --- | --- | --- |
| 1 | legacy | data/扫地机器人100问2.txt | all | 0b09b443860033ea7aa71dda0cf9105e243c1dd9e0694583f883efaf8e0c801a |
| 2 | service | service_kb/warranty_service.txt | all | 79cfd6104b7bacb28905a74dec582c14a43f06e1fe212b0245d437f22d00b508 |
| 3 | legacy | data/维护保养.txt | all | c7648c242b0ebaa343f0fa18df11fa7926c608ed07c413137f35a36f90b32d47 |
| 4 | service | service_kb/warranty_service.txt | all | efeacdb35c56148c4c1fbd1ae93488e5501eeee4f2f62e17a43fa936a4364374 |
| 5 | legacy | data/选购指南.txt | all | 636215c1fe7ca525bdec71e96705bf619add7ee5309c999f89d0ac331dc544f8 |

三个查询均为本阶段自拟问题，没有使用题集题面。每次Top-5符合型号筛选，未明确型号的查询只有all。仅做检索，不运行聊天或评分答案质量。

## 取舍与后续范围

- 适用型号严格来自冻结manifest，采用来源级标签；errors、warranty_service、consumables三个综合资料标为all，没有擅自推断章节标签或改冻结资料。
- 复用已有回答与来源治理，新增service路径和只读legacy入口。S1-A已记录的最终回答组装限制仍留S3共用渲染器解决，本阶段不跑dev评测。
- 修正引用捕获时机：生成使用哪些分块与提交检查逐块复核是不同集合操作，后者不会缩小实际引用集合。
- 首次CI的三项新增测试暴露了本机tokenizer与CI字节估算的差异：预算裁剪使拟撤销分块没有进入回答。已在测试中固定充足的离线预算和空模型，并明确断言目标分块已被使用；独立预算裁剪反例仍保留。生产预算、检索及治理实现未因此更改。
- 本机完整回归还发现微型临时Chroma/HNSW集合偶发丢失尚未持久化的读取器。治理单测改用假embedding和确定性的内存向量存储，仍执行真实SourceCatalog、分块、过滤、融合、回答和提交校验；真实持久化Chroma由102分块索引和三次实际检索验证。
- S1-B要求的真实索引、离线验证、legacy回放与治理均已完成。没有实施S2确认或S3计划/渲染。CI结果以PR检查为准，完成后在交付汇报补充。
