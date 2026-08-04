import json, urllib.request, urllib.error, sqlite3, sys

B = "http://127.0.0.1:8000"
fails, warns, oks = [], [], []

def call(method, path, body=None, raw=False):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(B + path, data=data,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read().decode("utf-8", "replace")
            return r.status, (b if raw else json.loads(b))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

def check(cond, name, detail=""):
    if cond:
        oks.append(name)
    else:
        fails.append(f"{name} :: {detail}")
    return cond

def warn(cond, name, detail=""):
    (oks if cond else warns).append(f"{name} :: {detail}")
    return cond

print("="*70)
print("QA-API 全面测试")
print("="*70)

# 1. health
st, body = call("GET", "/api/health")
check(st == 200 and body.get("status") == "ok", "GET /api/health", f"code={st} body={body}")

# 2. tools list
st, body = call("GET", "/api/tools")
ok = st == 200 and isinstance(body, dict) and isinstance(body.get("tools"), list) and len(body["tools"]) == 4
check(ok, "GET /api/tools (4 tools)", f"code={st} tools={len(body.get('tools',[])) if isinstance(body,dict) else 'n/a'}")

# 3. blue-ocean happy
st, bo_body = call("POST", "/api/blue-ocean/research",
                {"country": "US", "category": "Kitchen", "budget_usd": 5000})
tid = bo_body.get("task_id") if isinstance(bo_body, dict) else None
ok = st == 200 and isinstance(bo_body, dict) and bo_body.get("status") == "done"
check(ok, "POST /api/blue-ocean/research 正常( status=done )", f"code={st} status={bo_body.get('status') if isinstance(bo_body,dict) else bo_body}")
if isinstance(bo_body, dict):
    prods = bo_body.get("products", [])
    check(len(prods) == 10, "blue-ocean 返回10个产品", f"got {len(prods)}")
    if prods:
        p0 = prods[0]
        for k in ["product_name","market_size_monthly_usd","competition_level",
                  "opportunity_score","entry_recommendation","top_pain_points"]:
            check(k in p0, f"产品含字段 {k}", f"missing in {p0.get('product_name')}")
        # 评分排序校验
        asc = all(prods[i]["opportunity_score"] >= prods[i+1]["opportunity_score"] for i in range(len(prods)-1))
        check(asc, "产品按机会评分降序", f"order={[p['opportunity_score'] for p in prods]}")

# 4. blue-ocean 边界: 缺字段
st, body = call("POST", "/api/blue-ocean/research", {"country": "US"})
check(st == 422, "blue-ocean 缺 category/budget -> 422", f"code={st} body={body}")

# 5. tasks 历史查询
st, body = call("GET", f"/api/blue-ocean/tasks/{tid}")
check(st == 200 and isinstance(body, dict) and "products" in body,
      "GET /api/blue-ocean/tasks/{id}", f"code={st}")

# 6. agent/run 四类意图
cases = [
    ("market", "帮我找美国厨房类目预算5000美元的蓝海产品", lambda d: "market" in d and d["market"]),
    ("competitor", "分析一下 wireless earbuds 的竞品", lambda d: "competitor" in d and d["competitor"]),
    ("voc", "分析 cat water fountain 的用户评论痛点", lambda d: "voc" in d and d["voc"]),
    ("product", "判断一下 pets 类目 cat water fountain 是否值得做，预算3000", lambda d: "product" in d and d["product"]),
    ("unknown", "你好，今天天气不错", lambda d: d.get("intent") == "unknown" and d.get("clarification")),
]
for intent, q, fn in cases:
    st, body = call("POST", "/api/agent/run", {"query": q})
    ok = st == 200 and isinstance(body, dict) and fn(body)
    check(ok, f"agent/run 意图={intent}", f"code={st} body_keys={list(body.keys()) if isinstance(body,dict) else body}")

# 7. agent/run 空输入
st, body = call("POST", "/api/agent/run", {"query": ""})
check(st in (200, 400, 422), "agent/run 空query 不崩", f"code={st}")

# 8. tools 四个执行 (默认 mock) —— 返回包为 {"tool","backend","result"}
for name, inp in [
    ("amazon_research", {"country":"US","category":"Kitchen","budget_usd":5000,"top_n":5}),
    ("market_search", {"country":"US","category":"Pet","pool_size":20}),
    ("voc_analysis", {"niche_keyword":"cat water fountain","country":"US","top_n":5}),
    ("image_generation", {"product_name":"Cat Water Fountain","niche_keyword":"pets","style":"minimal","count":3,"platform":"amazon"}),
]:
    st, body = call("POST", f"/api/tools/{name}", {"input": inp})
    ok = st == 200 and isinstance(body, dict) and "result" in body
    check(ok, f"POST /api/tools/{name} (mock)", f"code={st} body={str(body)[:120]}")
    if ok:
        warn(isinstance(body["result"], dict),
             f"tools/{name} result 为对象", f"keys={list(body['result'].keys())[:5] if isinstance(body['result'],dict) else type(body['result'])}")

# 9. tools 缺 input 字段 -> 应校验 (voc 缺 niche_keyword)
st, body = call("POST", "/api/tools/voc_analysis", {"input": {"country":"US"}})
check(st in (400, 422), "tools 缺必填字段 -> 4xx", f"code={st}")

# 10. tools 未知工具 -> 404
st, body = call("POST", "/api/tools/not_exist", {"input": {}})
check(st == 404, "tools 未知工具 -> 404", f"code={st}")

# 11. tools api 后端未实现 -> 501
st, body = call("POST", "/api/tools/amazon_research",
                {"input":{"country":"US","category":"Kitchen","budget_usd":5000},"backend":"api"})
check(st == 501, "tools api 后端 -> 501", f"code={st}")

# 12. 数据库落库验证
db = sqlite3.connect("backend/amazon_growth_os.db")
nt = db.execute("select count(*) from research_tasks").fetchone()[0]
no = db.execute("select count(*) from product_opportunities").fetchone()[0]
check(nt > 0 and no > 0 and no % 10 == 0, "DB 落库 (tasks/opportunities, 10倍数)",
      f"tasks={nt} opps={no}")
db.close()

print("\n--- 结果 ---")
print(f"PASS : {len(oks)}")
print(f"WARN : {len(warns)}")
print(f"FAIL : {len(fails)}")
for w in warns: print("  ⚠", w)
for f in fails: print("  ✗", f)
sys.exit(1 if fails else 0)
