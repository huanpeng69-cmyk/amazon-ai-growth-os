# 真实数据架构改造 — 修改方案（待确认）

> 项目：Amazon AI Growth OS
> 目标：去除所有 Mock 业务数据，建立统一数据层
> `Data Source → Connector → Data Processing → Database → Agent`
> 状态：**方案阶段，确认后再开发**

---

## 一、现状盘点：要清除的 Mock / 编造数据

| # | 当前位置 | 编造方式 | 被谁使用 | 改造去向 |
|---|----------|----------|----------|----------|
| 1 | `mcp/research_mcp.py` | `random.Random(seed)` 确定性合成市场信号（搜索量/价格/卖家数/评论数/增速/痛点） | amazon_research、market_search、voc_analysis 三个 tool 的 Mock 后端；advertising/competitor 直接 import | **删除**，改由 `amazon_connector` + `keyword_connector` + `review_connector` 提供 |
| 2 | `tools/amazon_research/backends.py` `MockAmazonResearchBackend` | 调 research_mcp | Market Agent / 蓝海挖掘 | `amazon_connector` 后端 |
| 3 | `tools/market_search/backends.py` `MockMarketSearchBackend` | 调 research_mcp | Market/Keyword 分析 | `keyword_connector` 后端 |
| 4 | `tools/voc_analysis/backends.py` `MockVOCBackend` | 调 research_mcp | VOC Agent | `review_connector` 后端 |
| 5 | `agents/advertising/tools.py` | `random.Random` 编造 ACOS/ROAS/CTR/CVR/花费/订单 | Advertising Agent | `ads_connector` |
| 6 | `agents/competitor/tools.py` | `random.Random` 编造竞品价格/评论/份额 | Competitor Agent | `amazon_connector` |
| 7 | `agents/profit/sources.py` `SupplyChainConnector.is_mock=True` | 名称派生"看起来真实"的成本 | Profit 供应链来源 | 改为真实成本来源（见第十节） |
| 8 | `tools/image_generation/backends.py` `MockImageGenBackend` | 确定性返回图片方案 | 图片/视觉 Agent | `image_connector`（取真实商品/竞品/参考图） |
| 9 | `config_store.py` | `TOOL_BACKEND_*=mock` 默认走 mock 后端 | 全局后端选择 | 改为 connector 模式 |

**结论**：所有 `random`/`research_mcp` 调用必须从 Agent 与 tool 中移除，统一经 Connector → Processing → DB 取数。

---

## 二、目标架构

```
┌──────────────────────────────────────────────────────────────────────┐
│ Data Source（真实外部源）                                              │
│  Amazon SP-API · 评论API · 关键词工具(Helium10/SellerSprite) ·        │
│  Advertising API · 图片CDN/图库 · 用户上传的真实文件                   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ (凭证 / 或 真实样本数据集 fixture)
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Connector（backend/app/data/connectors/）                              │
│  amazon_connector · review_connector · keyword_connector ·            │
│  ads_connector · image_connector                                       │
│  每个 Connector：fetch(query) → RawData（原始响应，仅搬运不加工）       │
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Data Processing（backend/app/data/processing/）                        │
│  parse_* ：原始 → 结构化领域模型；字段校验 / 货币·百分比·时间归一       │
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Database（SQLAlchemy + SQLite/PostgreSQL）                             │
│  raw_fetches（缓存原始响应）· products · reviews · keyword_metrics ·  │
│  ad_metrics · image_assets（复用 research_tasks / product_opportunities）│
└───────────────────────────┬──────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Agent（backend/app/agents/*）                                          │
│  禁止直接生成/编造数据；只能通过 dal.get_*(...) 从 DB 取数             │
│  （DB 无缓存时 DAL 自动触发 Connector→Processing→落库）               │
└──────────────────────────────────────────────────────────────────────┘
```

**关键约束**：Agent 永远不直接调用 `random` / `research_mcp` / 外部 API / `random` 派生；唯一取数入口是 `dal`（Data Access Layer）。

---

## 三、新增目录结构

```
backend/app/data/
  __init__.py
  base.py            # BaseConnector / RawData / ConnectorAdapter 抽象
  registry.py        # ConnectorRegistry：按名取 Connector 实例
  schemas.py         # RawData + 各领域 Processed 模型（Pydantic）
  dal.py             # Data Access Layer：Agent 唯一取数入口（含缓存回源逻辑）
  exceptions.py      # ConnectorError / NotConfigured / DataNotFound
  connectors/
    __init__.py
    amazon_connector/  { connector.py, schemas.py, adapters/{live.py,fixture.py}, fixtures/sample.json }
    review_connector/  { connector.py, schemas.py, adapters/{live.py,fixture.py}, fixtures/sample.json }
    keyword_connector/ { connector.py, schemas.py, adapters/{live.py,fixture.py}, fixtures/sample.json }
    ads_connector/     { connector.py, schemas.py, adapters/{live.py,fixture.py}, fixtures/sample.json }
    image_connector/   { connector.py, schemas.py, adapters/{live.py,fixture.py}, fixtures/ }
  processing/
    __init__.py
    parse_amazon.py  parse_review.py  parse_keyword.py  parse_ads.py  parse_image.py
```

> 现有 `tools/*/backends.py` 的 Mock 实现将被 Connector 调用替换；`mcp/research_mcp.py` 删除。
> 现有 `tools/base.py` 的 `BackendType`(MOCK/MCP/API/LOCAL_MODEL) 抽象**保留并复用**，作为 Connector 内部 adapter 的选型机制。

---

## 四、五个 Connector 规格

### 1. amazon_connector（亚马逊商品/市场数据）
- **fetch 输入**：`{asin? , keyword?, country, category?}`
- **返回 RawData**：商品标题、价格、BSR、月销量估算、卖家数、评分、评论数、类目
- **真实数据源**：Amazon SP-API（Catalog Items / Product Pricing / Sales）+ Keepa（历史销量）
- **fixture**：`fixtures/sample.json`（真实导出的商品快照）

### 2. review_connector（评论 / VOC）
- **fetch 输入**：`{asin, country, max_reviews?}`
- **返回 RawData**：评论列表（评分、正文、日期、是否 VP、痛点关键词）
- **真实数据源**：Amazon 评论 API / 第三方评论抓取（如 easy-amazon-voc）
- **fixture**：`fixtures/sample.json`（真实评论样本）

### 3. keyword_connector（搜索词 / 流量）
- **fetch 输入**：`{seed_keyword, country}`
- **返回 RawData**：关键词、月搜索量、竞品浓度、CPC、趋势
- **真实数据源**：Helium 10 / SellerSprite / 卖家精灵 关键词接口
- **fixture**：`fixtures/sample.json`

### 4. ads_connector（广告 / PPC）
- **fetch 输入**：`{asin? , campaign_id?, country, date_range?}`
- **返回 RawData**：ACOS、ROAS、CTR、CVR、花费、广告销售额、订单、关键词表现
- **真实数据源**：Amazon Advertising API（Sponsored Products/Brands/Display 报表）
- **fixture**：`fixtures/sample.json`

### 5. image_connector（图片 / 视觉素材）
- **fetch 输入**：`{asin?, query?, kind: product|competitor|reference}`
- **返回 RawData**：图片 URL 列表、尺寸、来源
- **真实数据源**：Amazon 商品图 CDN / 图库 API（如 Unsplash）/ 用户上传
- **fixture**：`fixtures/` 下静态资源（提供本地参考图，用于视觉生成前的数据输入）

> 每个 Connector 统一形如：
> `BaseConnector.fetch(query: dict) -> RawData`，内部按配置选 `LiveAdapter`（需凭证）或 `FixtureAdapter`（真实样本数据集）。

---

## 五、Data Processing（原始 → 结构化）

`processing/parse_*.py` 各自把 RawData 转成 `data/schemas.py` 中的领域模型，并做：
- 字段校验（缺失关键字段 → 抛 `DataNotFound`）
- 归一化：货币统一 USD、比率统一 0–1、时间戳统一 ISO8601
- 去重与基础清洗（评论去噪、关键词小写归一）

产出即写入 DB 的 `products / reviews / keyword_metrics / ad_metrics / image_assets`。

---

## 六、数据库设计（新增表，复用现有 engine）

| 表 | 关键字段 | 说明 |
|----|----------|------|
| `raw_fetches` | id, connector, query_hash, payload(JSON), fetched_at | Connector 原始响应缓存，避免重复拉取 |
| `products` | asin, country, title, price, bsr, est_monthly_sales, sellers, rating, review_count, category, source |
| `reviews` | id, asin, country, rating, body, is_vp, reviewed_at, pain_keywords(JSON) |
| `keyword_metrics` | id, seed_keyword, country, keyword, search_volume, competition, cpc, trend |
| `ad_metrics` | id, asin, country, acos, roas, ctr, cvr, spend, ad_sales, orders, period_start, period_end |
| `image_assets` | id, kind, asin, url, width, height, source |

复用：`research_tasks` / `product_opportunities` / lifecycle 表。`init_db()` 自动建表（演示）；生产用 `db/schema.sql` 迁移。

---

## 七、Agent 改造映射（去 Mock）

| Agent | 删除 | 改为调用 DAL |
|-------|------|--------------|
| `market` / 蓝海挖掘 | `research_mcp` 合成 | `dal.get_market(country,category)` = amazon + keyword + review 聚合 |
| `competitor` | `random` 编造竞品 | `dal.get_competitor(asin,country)` ← amazon_connector |
| `voc` | `research_mcp` 痛点 | `dal.get_reviews(asin,country)` ← review_connector |
| `advertising` | `random` 编造 ACOS 等 | `dal.get_ads(asin,country)` ← ads_connector |
| `product` | `research_mcp` | `dal.get_product(asin,country)` ← amazon_connector |
| `profit` | `SupplyChainConnector(is_mock)` | 成本来源 = 用户手动 / Excel 上传（真实用户数据）；平台费(FBA/佣金)可由 `amazon_connector` 真实费率表提供（见第十节） |
| `image` / `visual_agent` | `MockImageGenBackend` | `dal.get_images(...)` ← image_connector（真实图作为输入） |
| `supervisor` / `sales_forecast` / `risk` | 不变（纯计算/编排，不编造业务数据） | 只读 DAL 结果 |

**DAL 契约示例**：
```python
def get_ads(asin, country, force_refresh=False) -> AdMetric:
    cached = db.query(AdMetric).filter_by(asin=asin, country=country).first()
    if cached and not force_refresh: return cached
    raw = ConnectorRegistry.get("ads").fetch({"asin": asin, "country": country})
    processed = parse_ads(raw)
    db.add(processed); db.commit()
    return processed
```

---

## 八、配置与前端

- `config_store.py`：后端默认由 `mock` 改为 `connector`；新增每个 Connector 的凭证字段（API Key / 区域 / 端点）。
- 设置页（`#/settings`）：可填各 Connector 凭证；切换 `fixture ↔ live`；显示各 Connector 健康状态。
- 产品空间 / 各报告：增加**数据溯源徽标**（"数据来源：amazon_connector @ 2026-08-01"），强化"真实数据驱动"。

---

## 九、实施阶段（分步，每步可独立验证）

- **Phase 0 — 地基**：`data/base.py` `registry.py` `schemas.py` `dal.py` `exceptions.py`；DB 新表；`config_store` 改造。
- **Phase 1 — Connectors**：5 个 Connector（接口 + FixtureAdapter + LiveAdapter 骨架）；删除 `research_mcp.py` 与 `tools/*/Mock*Backend`。
- **Phase 2 — Processing**：5 个 `parse_*` + 校验。
- **Phase 3 — DB 落库**：DAL 回源写库；`raw_fetches` 缓存。
- **Phase 4 — Agent 改造**：按第七节逐个去掉 `random`/`research_mcp`，改调 DAL（先 advertising/competitor/voc，再 market/product/profit/image）。
- **Phase 5 — 配置与前端**：设置页凭证/切换；数据溯源徽标。
- **Phase 6 — 验证**：全仓 `grep` 确认无 `random`/`research_mcp`/`Mock` 残留于数据路径；5 个 Connector fixture 返回真实数据；Agent 报告均出自 DB。

---

## 十、需你拍板的开放问题

1. **无真实凭证时的数据来源（最关键）**
   去除 Mock 后，若暂未接入真实 API：
   - **(A) 混合模式（推荐）**：默认加载**真实样本数据集（fixture，非随机编造）**，配置凭证后自动切真实 API。系统可运行、架构真实，且数据非"Mock 业务数据"。
   - **(B) 纯实时**：只接真实 API，无凭证即报错（系统暂时无法演示）。
   - **(C) 仅契约**：只搭 Connector 接口与 DB，业务数据由用户手动上传/提供（最"纯净"，但缺即开即用体验）。

2. **供应链成本（Profit 模块）**：利润测算的成本来源不在 5 个 Connector 内。建议保留「手动输入 / Excel 上传」（均为用户真实数据），平台费(FBA/佣金)改由 `amazon_connector` 真实费率表提供；是否仍需一个独立的 `supply_chain_connector`？

3. **凭证现状**：当前是否有可用的 Amazon / 关键词 / 广告 API 凭证？有则可直接落地 LiveAdapter；无则 Phase 1 先以 FixtureAdapter + 真实契约骨架交付。

---

> 请确认方案与第十节三项决策，确认后我开始按 Phase 0→6 开发。

---

## 实施状态（更新于 2026-08-01）

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 数据层地基（base/exceptions/schemas/registry/models/dal + config_store 注册） | ✅ 完成 |
| Phase 1 | 5 个 Connector + 删除核心 Mock（research_mcp / SupplyChainConnector） | ✅ 完成 |
| Phase 2 | Data Processing 解析层 | ✅ 完成 |
| Phase 3 | DAL 回源落库（含容错 + raw_fetches 溯源） | ✅ 完成 |
| Phase 4 | Agent 改造去 Mock（market/competitor/voc/advertising/product + 3 个 tool 后端） | ✅ 完成 |
| Phase 5 | 配置与前端：设置页 Connector 凭证/模式/健康状态 + 报告数据溯源徽标 | ✅ 完成 |
| Phase 6 | 验证：grep 无残留；5 Connector fixture 真实；Agent 报告出自 DB；重启服务验证 | ✅ 完成 |

**Phase 5/6 交付要点**
- 新增 `backend/app/routers/data.py`：`GET /api/data/connectors`（健康探针+缓存统计）、`GET /api/data/provenance`（来源+回源时间）。
- `BaseConnector.fetch` 改为 live 优先、未就绪自动降级 fixture 的模板方法（避免配置错误时整条链路崩溃）。
- 前端设置页新增「统一数据层 · Connectors」卡片（模式切换 + 5 凭证 + 健康面板）；6 类报告页新增「数据溯源」徽标。
- 清理利润页 supply_chain 残留（与已删除的 SupplyChainConnector 一致）。
- 服务运行于 `http://127.0.0.1:8002/`，数据层全部经 Connector → Processing → DB → DAL → Agent，无任何随机/合成业务数据。
