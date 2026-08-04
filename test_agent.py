import json, urllib.request

B = "http://127.0.0.1:8000"


def run(q):
    req = urllib.request.Request(
        B + "/api/agent/run",
        data=json.dumps({"query": q}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return {"_error": e.read().decode()[:300]}


print("=== 1 MARKET (中文) ===")
d = run("帮我找美国厨房类目预算5000美元的蓝海产品")
print("intent:", d.get("intent"), "| reason:", d.get("plan_reason"))
if d.get("market"):
    m = d["market"]["opportunities"][0]
    print("top1:", m["product_name"], "score", m["opportunity_score"], "| count", len(d["market"]["opportunities"]))

print("=== 2 COMPETITOR ===")
d = run("分析一下 wireless earbuds 的竞品")
print("intent:", d.get("intent"), "| reason:", d.get("plan_reason"))
if d.get("competitor"):
    c = d["competitor"]["competitors"][0]
    print("top:", c["name"], "share", c["est_market_share"], "weak:", c["weakness"])

print("=== 3 VOC ===")
d = run("分析 cat water fountain 的用户评论痛点")
print("intent:", d.get("intent"))
if d.get("voc"):
    p = d["voc"]["pain_points"][0]
    print("top pain:", p["pain"], p["severity"], "| fix:", p["suggested_fix"])

print("=== 4 PRODUCT ===")
d = run("判断一下 pets 类目 cat water fountain 是否值得做，预算3000")
print("intent:", d.get("intent"))
if d.get("product"):
    p = d["product"]
    print("verdict:", p["verdict"], "score", p["opportunity_score"], "| pos:", p["recommended_positioning"])

print("=== 5 UNKNOWN ===")
d = run("你好")
print("intent:", d.get("intent"), "| clarification:", d.get("clarification"))
