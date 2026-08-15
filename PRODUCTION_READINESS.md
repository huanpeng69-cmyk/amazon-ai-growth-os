# Amazon AI Growth OS —— 生产级就绪跟踪文档

> 状态：评估完成，待逐项推进。最后更新：2026-08-04
> 方法：Aegis 有界扫描（README/基线 + 定点取证），未通读全部 143 个源文件。
> 结论：**业务正确性（数据真实性）已修复；工程化 / 运维 / 安全层面距生产仍有较大缺口。**

## 跟踪总览（勾选推进）

### P0 — 上线前阻塞项
- [x] P0-1 建立测试套件（pytest）+ GitHub Actions CI（lint/type/test 门禁）
  - 交付：`backend/tests/{test_agnes,test_util,test_agents_honest_degradation}.py`（共 32 用例，全绿）；
    `backend/pytest.ini`（pythonpath）、`backend/pyproject.toml`（ruff/mypy 配置）、
    `backend/requirements-dev.txt`、` .github/workflows/ci.yml`。
  - **门禁范围**：`ruff` 当前只把「真实正确性」（`F`/`E`/`W`）纳入硬性门禁，风格类（`UP`/`I`/`B`/`SIM`/`E501`/`E402`/`E702`）暂忽略，避免无谓重构；`mypy` 当前为**允许失败的信息性步骤**（全仓 143 文件基本无类型标注，共 114 处类型不一致，含若干潜在真实 bug 如 `lifecycle/service.py` 访问不存在的 `MarketOutput.title`），待 P1-4 / P2-4 收紧。
- [x] P0-2 API 认证 / 授权中间件（Bearer/API Key；写操作强制 token）
  - 交付：`backend/app/security.py`（`get_current_key` 依赖，支持 Bearer / X-API-Key / `?api_key`）；
    `main.py` 对所有业务路由（agent/blue_ocean/tools/lifecycle/workspace/profit/data）统一挂该依赖，
    `/api/health` 与 `/` 静态开放；`API_AUTH_TOKEN` 仅在配置时强制（未配置保持开放，向后兼容）。
  - 测试：`backend/tests/test_auth.py`（6 用例，TestClient 验证开放/401/Bearer/X-API-Key/query/错误 Key）。
  - 验收：未配 key 调用业务接口 200；配 key 无令牌 401；配 key 且正确令牌放行。
- [ ] P0-3 速率限制 / 配额（slowapi+redis；Bright Data 重试+退避+并发信号量）
- [ ] P0-4 可复现构建（Dockerfile + 版本锁定 + gunicorn 多 worker）

### P1 — 重要（稳定性 / 可观测性）
- [ ] P1-1 全局异常处理 + 统一 JSON 错误包（含 trace_id）
- [ ] P1-2 集中日志 + 链路追踪（dictConfig 结构化日志 + 请求 ID）
- [ ] P1-3 数据库迁移（PostgreSQL + Alembic；替换手动 `_migrate`）
- [ ] P1-4 同步阻塞治理 + 请求整体超时（asyncio 并发 / 超时熔断）
- [ ] P1-5 生产配置硬化（`/docs` 关闭、CORS 收紧）

### P2 — 优化项
- [ ] P2-1 结果缓存层（keyword+country TTL）
- [ ] P2-2 前端构建 / 打包（Vite + 哈希 + CSP）
- [ ] P2-3 API 版本化（`/api/v1`）
- [ ] P2-4 配置校验（pydantic-settings）
- [ ] P2-5 image agent 接真实生图后端（去掉默认 mock）

---

## 已具备的优势（勿回退）

| 项 | 说明 | 证据 |
|---|---|---|
| Agent 数据真实性 | 真实 Bright Data 抓取 + 真实评论 + 大模型合成；无数据诚实降级 | 本次修复成果 |
| CORS 白名单 | 默认回环地址 + 可配 `CORS_ALLOW_ORIGINS`，非通配 | `backend/app/main.py:90-122` |
| LLM 调用韧性 | `agnes.chat` 统一 `AgnesError` + 自动重试 3 次 | `backend/app/llm/agnes.py` |
| 健康检查 | `/api/health` 返回 `{status, service}` | `backend/app/main.py:134` |
| 配置安全 | 密钥 GET 脱敏；写操作可选 `SETTINGS_API_TOKEN` | `backend/app/config_store.py`、`routers/settings.py:29-48` |
| 数据层抽象 | connector 模式 `auto/live/fixture`，便于切换数据源 | `backend/app/config_store.py` `_CONFIG_SPEC` |

---

## P0 — 上线前阻塞项

### P0-1 测试套件 + CI
- **问题**：无 `tests/` 目录，仅有根目录手写脚本 `qa_test.py` / `test_agent.py` / `test_tools.py`（需手动跑，非回归保护）；无 `.github/workflows`。
- **影响**：任何改动都可能悄悄回归（"编造数据"类问题正是因无回归测试而长期潜伏）。
- **建议方案**：
  - 引入 `pytest`，按 `backend/tests/{unit,integration}` 组织；优先覆盖：`agnes` 异常/重试、各 agent 的"无数据诚实降级"契约、`extract_json` 解析、竞品 `est_market_share` 永不为伪造值。
  - 加 GitHub Actions：`.github/workflows/ci.yml`，步骤 = `ruff` lint + `mypy` 类型（信息性）+ `pytest`。
- **验收标准**：`pytest` 在 CI 全绿；新增 agent 改动必须带对应测试；CI 拦截 lint/type 错误。
- **✅ 已完成（2026-08-04）**：测试套件 32 用例全绿（含 agnes 重试/异常回归、各 agent 诚实降级契约、`extract_json`）；
  CI 已落地，`ruff` 为硬性门禁、`mypy` 为信息性步骤。详见上方总览 P0-1 注释。

### P0-2 认证 / 授权
- **问题**：除 settings 可选 token 外，所有 `/api/agent`、`/api/data`、`/api/blue-ocean` 等端点完全开放（`backend/app/main.py` 仅挂载 `CORSMiddleware`，无 auth 中间件）。
- **影响**：一旦对外暴露，任何人可调用并**烧 Bright Data / Agnes 按量额度**；数据写接口无保护。
- **建议方案**：
  - 加 `FastAPI` 依赖 `get_current_key`：校验 `Authorization: Bearer <API_KEY>` 或 `X-API-Key` 头；密钥存环境变量/`config_store`，不进代码。
  - 全局默认要求 key；`/api/health`、`/` 静态资源可放行。
  - settings 写接口（`PUT /api/settings`）强制 `SETTINGS_API_TOKEN`（现有机制复用并强化）。
- **验收标准**：无有效 key 调用 agent 接口返回 401；写配置无 token 返回 403。
- **✅ 已完成（2026-08-04）**：见上方总览 P0-2 注释。`get_current_key` 已挂到全部业务路由；`API_AUTH_TOKEN` 仅在配置时强制，未配置保持本地开放。settings 写接口沿用 `SETTINGS_API_TOKEN`（本项未改动其逻辑）。

### P0-3 速率限制 / 配额
- **问题**：
  - 端点无节流；外部依赖按量计费，高频调用会烧钱 + 触发 429。
  - **Bright Data 客户端只有 timeout、无重试、无 429 退避、无并发控制**（`backend/app/mcp/brightdata_client/client.py:81,111,191` 仅 `timeout=60`）。
- **建议方案**：
  - API 层加 `slowapi` 限流（按 IP/key，如 20 req/min）；重操作（agent run）单独配额。
  - Bright Data 客户端加：指数退避重试（尊重 `Retry-After`/429）、并发 `Semaphore`、超时统一。
- **验收标准**：压测下单 key 超阈值返回 429；BD 瞬时 429 自愈不报错。

### P0-4 可复现构建 / 部署
- **问题**：`requirements.txt` 全 `>=`、零版本锁定（grep 命中 0 个 `==`）；无 `Dockerfile`；`gunicorn` 在 requirements 被注释。
- **影响**：构建不可复现，依赖漂移/供应链风险；无标准部署形态。
- **建议方案**：
  - 加 `Dockerfile`（python:3.13-slim + `pip install -r requirements.lock` + `gunicorn -k uvicorn.workers.UvicornWorker -w N`）。
  - 生成锁定文件（pip-tools `requirements.lock` 或 `poetry.lock`）；取消注释并启用 `gunicorn`。
  - 提供 `docker-compose.yml`（app + postgres + redis[限流用]）。
- **验收标准**：`docker build` + `docker run` 一条命令起服务；依赖版本锁定可复现。

---

## P1 — 重要（稳定性 / 可观测性）

### P1-1 全局异常处理 + 统一错误包
- **问题**：仅 `routers/agent.py` 有少量 `HTTPException(502/400)`；其余异常直接 500，无一致 JSON 错误体。
- **建议方案**：加 `app.add_exception_handler(Exception, ...)` + `HTTPException` handler，统一返回 `{"error": "internal"|"bad_request", "detail": ..., "trace_id": ...}`；非生产环境才带堆栈。
- **验收标准**：任意未捕获异常返回统一 JSON（非 HTML），含 `trace_id`；生产不泄露内部细节。

### P1-2 集中日志 + 链路追踪
- **问题**：全项目仅 `logging.getLogger`，无 `basicConfig/dictConfig`、无 format/级别/轮转/请求 ID（`backend/app/**` grep 无 `dictConfig`）。排障靠 `server.log` 裸输出。
- **建议方案**：`logging.dictConfig` 结构化(JSON) 日志；请求 ID 中间件（`X-Request-ID`）；可选 OpenTelemetry 接入。
- **验收标准**：日志为 JSON、带 `request_id`/`trace_id`/时间戳/级别；可按请求 ID 串联一次调用链。

### P1-3 数据库迁移
- **问题**：默认 SQLite（`backend/app/database.py` `DATABASE_URL`）；`init_db()` 用 `create_all`；`main.py:_migrate()` 仅硬编码 2 个列的 `ALTER`（`category`/`platform`），schema 演进脆弱。无 Alembic；`db/schema.sql`（PostgreSQL）未用上。
- **建议方案**：生产切 PostgreSQL；引入 Alembic（`alembic init`，`env.py` 读 `DATABASE_URL`）；现有 `_migrate` 逻辑迁移为首个迁移脚本。
- **验收标准**：`alembic upgrade head` 可重建最新 schema；新增列走迁移而非手工 ALTER。

### P1-4 同步阻塞治理 + 请求超时
- **问题**：agent 串行调外部（Bright Data + LLM，单次 30–60s），跑在 uvicorn threadpool；无整体请求超时；supervisor 编排多 agent 无超时（grep 无 `timeout/asyncio/gather`）。并发请求会排队/耗尽 worker。
- **建议方案**：加全局/路由级请求超时（如 `async def` + `asyncio.wait_for` 或网关超时）；agent 间可并发的外部调用用 `asyncio.gather`；Bright Data/LLM 调用加超时与取消。
- **验收标准**：超长 agent 调用在 N 秒后熔断返回 504/降级；并发 10 请求不耗尽线程。

### P1-5 生产配置硬化
- **问题**：`/docs` 未关闭；CORS `allow_methods/headers=["*"]` 偏宽；`.env` 写回逻辑需注意文件权限。
- **建议方案**：`FastAPI(docs_url=None)` 在生产（`ENV=production`）关闭 `/docs` `/redoc`；CORS methods/headers 收敛为实际所需；settings 写回 `.env` 限制权限（0600）。
- **验收标准**：生产环境 `/docs` 404；CORS 仅放行声明的方法/头。

---

## P2 — 优化项

### P2-1 结果缓存层
- **问题**：每次请求都打 Bright Data + LLM，慢且贵（grep 全局无 cache 层）。
- **建议方案**：按 `keyword+country+limit` 加 TTL 缓存（如 `cachetools`/Redis）；复用已抓评论；区分"实时模式"与"缓存模式"。
- **验收标准**：相同检索命中缓存，BD/LLM 调用次数显著下降；TTL 可配。

### P2-2 前端构建 / 打包
- **问题**：`frontend/` 为 vanilla 静态 SPA（`index.html` + `assets/js/*.js`），无 `package.json`/Vite/打包/压缩/哈希/CSP。
- **建议方案**：引入 Vite 构建（minify + 资源哈希 + sourcemap 管理）；加 `Content-Security-Policy` 响应头；`dist/` 作为构建产物。
- **验收标准**：`npm run build` 产出带哈希的压缩资源；CSP 生效。

### P2-3 API 版本化
- **问题**：`/api/agent` 等无版本前缀，迭代会破坏前端。
- **建议方案**：路由加 `/api/v1` 前缀（保持旧路径重定向或并行一期）。
- **验收标准**：新接口带 `/api/v1`；前端调用统一走 v1。

### P2-4 配置校验
- **问题**：`config_store` 全字符串、无 pydantic-settings 校验；类型/范围错误只在运行时暴露。
- **建议方案**：引入 `pydantic-settings`；对 `AGNES_TIMEOUT`（int>0）、`CORS_ALLOW_ORIGINS`（list）等做校验与默认值归一。
- **验收标准**：非法配置在启动时/写入时即报错，而非运行时崩溃。

### P2-5 image agent 真实化
- **问题**：`TOOL_BACKEND_IMAGE_GENERATION` 默认 `mock`，生图不走真实链路（之前审计标记未改）。
- **建议方案**：接入真实生图后端（WisArt/`AGNES_IMAGE_MODEL`），保留 mock 作为离线兜底；输出走统一数据层。
- **验收标准**：配置真实后端后生图返回真实图片 URL；mock 仅离线可用。

---

## 建议执行顺序
1. **P0-1（测试+CI）** —— 先建质量门禁，后续每步改动都有回归保护。
2. **P0-2 + P0-3（认证+限流）** —— 决定"能否放心对外"，且保护按量计费额度。
3. **P0-4（Docker+锁定）** —— 让部署可复现、可水平扩展。
4. **P1（日志/异常/迁移/超时/硬化）** —— 提升可观测性与稳定性。
5. **P2（缓存/前端/版本化/校验/image）** —— 性能与体验优化。

> 每完成一项，在上方"跟踪总览"勾选并单独提交（commit message 标注 `P0-x`/`P1-x`），便于回溯。
