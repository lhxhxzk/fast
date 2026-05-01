import urllib.request
import json
import sqlite3
import time

print("=" * 60)
print("API 测试：POST /orders（使用 dataclass 事件类）")
print("=" * 60)

from uuid import uuid4

order_id = f"ORD-{uuid4().hex[:8]}"
data = json.dumps({"order_id": order_id, "product_name": "Widget", "quantity": 5}).encode()
req = urllib.request.Request("http://127.0.0.1:8001/orders", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req)
    body = json.loads(resp.read())
    print(f"\n请求 order_id: {order_id}")
    print(f"响应状态码: {resp.status}")
    print(f"响应体: {json.dumps(body, ensure_ascii=False, indent=2)}")
except urllib.error.HTTPError as e:
    print(f"\n请求失败: HTTP {e.code}")
    print(json.loads(e.read()))
    exit(1)

time.sleep(2)

print("\n" + "=" * 60)
print("数据库验证")
print("=" * 60)

conn = sqlite3.connect("manufacturing.db")
c = conn.cursor()

print("\n--- production_tasks 表 ---")
c.execute("SELECT task_id, order_id, product_name, quantity, status FROM production_tasks")
rows = c.fetchall()
print(f"  记录数: {len(rows)}")
for row in rows:
    print(f"  task_id={row[0]}, order_id={row[1]}, product_name={row[2]}, quantity={row[3]}, status={row[4]}")

print("\n--- event_logs 表 ---")
c.execute("SELECT event_type, status, payload FROM event_logs")
for row in c.fetchall():
    print(f"  event_type={row[0]}, status={row[1]}")
    print(f"  payload={row[2][:120]}...")

conn.close()

print("\n" + "=" * 60)
if len(rows) > 0:
    print("✅ dataclass 版本验收通过：订单API自动创建了生产任务记录")
else:
    print("❌ 验收失败")
print("=" * 60)
