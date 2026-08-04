"""MCP Tool 层接口联调：4 个工具 input JSON -> output JSON。"""
import json
import urllib.request

B = "http://127.0.0.1:8000"


def run(name, payload, backend=None):
    body = {"input": payload}
    if backend:
        body["backend"] = backend
    req = urllib.request.Request(
        f"{B}/api/tools/{name}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_detail": json.load(e).get("detail")}


print("=== 1) amazon_research (mock) ===")
r = run("amazon_research", {"country": "US", "category": "Kitchen", "budget_usd": 5000, "top_n": 10})
res = r["result"]
print("backend:", r["backend"], "| opportunities:", len(res["opportunities"]))
print("  top1:", res["opportunities"][0]["product_name"], "score", res["opportunities"][0]["opportunity_score"])

print("=== 2) market_search (mock) ===")
r = run("market_search", {"country": "DE", "category": "Pets", "pool_size": 5})
res = r["result"]
print("backend:", r["backend"], "| signals:", len(res["signals"]))
print("  signal[0]:", res["signals"][0]["product_name"], "vol", res["signals"][0]["search_volume_monthly"])

print("=== 3) voc_analysis (mock) ===")
r = run("voc_analysis", {"niche_keyword": "cat water fountain", "country": "US", "top_n": 3})
res = r["result"]
print("backend:", r["backend"], "| pains:", len(res["pain_points"]))
for p in res["pain_points"]:
    print(f"  - {p['pain']} sev{p['severity']} ev{p['evidence']} -> {p['suggested_fix'][:40]}")
print("  summary:", res["summary"][:70])

print("=== 4) image_generation (mock) ===")
r = run("image_generation", {"product_name": "Cat Water Fountain", "niche_keyword": "pet hydration", "count": 4})
res = r["result"]
print("backend:", r["backend"], "| images:", len(res["images"]))
for img in res["images"]:
    print(f"  - {img['scene']} ({img['aspect_ratio']}): {img['prompt'][:55]}...")

print("=== 5) 替换能力演示：amazon_research -> api (未配置应 501) ===")
r = run("amazon_research", {"country": "US", "category": "Kitchen"}, backend="api")
print("  http:", r.get("_http"), "| detail:", r.get("_detail"))

print("=== 6) 输入校验演示：缺字段应 400 ===")
r = run("amazon_research", {"country": "US"})
print("  http:", r.get("_http"), "| detail:", str(r.get("_detail"))[:80])

print("=== 7) 契约查询 GET /api/tools ===")
req = urllib.request.Request(f"{B}/api/tools")
lst = json.load(urllib.request.urlopen(req, timeout=10))
for t in lst["tools"]:
    print(f"  {t['name']:16} backends={t['backends']} | input keys={list(t['input_schema'].get('properties', {}).keys())}")
