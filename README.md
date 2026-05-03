# 事件驱动制造业协调模块

## 模块定位

本模块是制造业系统中的**事件驱动协调层**，负责在订单、生产、采购三个业务子系统之间实现自动化的消息传递与流程联动。其他模块只需通过 HTTP API 下达订单，本模块即可自动完成下游任务的创建与协调。

## 快速启动

### 1. 安装依赖

打开终端，进入项目目录，执行：

```bash
cd "c:\Users\火影\Desktop\fast"
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python -m uvicorn main:app --workers 1 --port 8000
```

启动成功后，终端会显示：

```
INFO:event_bus:已注册处理器: OrderCreatedEvent -> handle_order_created
INFO:event_bus:已注册处理器: ProductionTaskCreatedEvent -> handle_production_task_created
INFO:event_bus:已注册处理器: PurchaseNeededEvent -> handle_purchase_needed
INFO:main:所有事件处理器注册成功
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> **注意**：必须使用 `--workers 1`，避免多线程并发写入 SQLite。

### 3. 调用订单 API（另开一个终端窗口）

**健康检查：**

```bash
python -c "import requests; print(requests.get('http://127.0.0.1:8000/').json())"
```

**创建订单（quantity=5，不触发采购）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-001','product_name':'Widget','quantity':5}).json())"
```

**创建订单（quantity=15，自动触发采购链）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-002','product_name':'Gadget','quantity':15}).json())"
```

**重复下单测试（返回 409）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-001','product_name':'Widget','quantity':5}).status_code)"
```

**负数库存测试（手动事务回滚）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-NEG','product_name':'Defective','quantity':-5}).json())"
```

等待 2 秒后查看数据库，确认无脏数据：

```bash
python -c "from database import SessionLocal; from models import *; db=SessionLocal(); print('Order:', db.query(Order).filter(Order.order_id=='ORD-NEG').first()); print('ProductionTask:', db.query(ProductionTask).filter(ProductionTask.order_id=='ORD-NEG').first()); log=db.query(EventLog).filter(EventLog.event_type=='OrderCreatedEvent').first(); print('EventLog:', log.status if log else 'None'); db.close()"
```

### 4. 异常场景测试

**超时模拟（product_name="SLOW"）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-SLOW','product_name':'SLOW','quantity':5}).json())"
```

handler 等待 5 秒，超过 3 秒超时阈值，自动回滚。服务端日志：

```
INFO:handlers:模拟超时: product_name=SLOW, 等待5秒...
ERROR:main:后台处理事件超时: elapsed=5.0s > timeout=3s, order_id=ORD-SLOW
INFO:main:手动回滚: 已删除订单 ORD-SLOW
INFO:main:事件已处理
```

**重复提交（相同 order_id）：**

```bash
python -c "import requests; r1=requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-DUP','product_name':'Widget','quantity':3}); print('第1次:', r1.status_code); r2=requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-DUP','product_name':'Widget','quantity':3}); print('第2次:', r2.status_code, r2.json())"
```

第 2 次返回 409，前端提示：`⚠️ 重复提交: 订单 ORD-DUP 已存在`

**网络失败模拟（product_name="NETFAIL"）：**

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:8000/orders', json={'order_id':'ORD-NET','product_name':'NETFAIL','quantity':5}).json())"
```

handler 调用不存在的库存服务（127.0.0.1:9999），连接超时后回滚。服务端日志：

```
INFO:handlers:模拟网络失败: product_name=NETFAIL, 调用不存在的库存服务...
ERROR:event_bus:处理器 handle_order_created 处理事件 OrderCreatedEvent 失败: 库存服务不可用: HTTPConnectionPool(host='127.0.0.1', port=9999): Max retries exceeded...
INFO:main:手动回滚: 已删除订单 ORD-NET
INFO:main:事件已处理
```

### 5. 查看日志验证

回到第一个终端窗口（运行服务的那个），你会看到：

**正常下单日志：**

```
INFO:main:事件已提交          ← 订单和事件日志已写入数据库
INFO:handlers:生产任务已创建: task_id=..., order_id=ORD-001
INFO:handlers:生产任务创建完成, 数量<=10, 无需采购
INFO:main:事件已处理          ← 后台事件处理完成
```

**"事件已提交"** 和 **"事件已处理"** 两条日志是验收关键标志。

### 6. 查看数据库

```bash
python -c "from database import SessionLocal; from models import *; db=SessionLocal(); print('=== orders ==='); [print(f'  {o.order_id} | {o.product_name} | qty={o.quantity}') for o in db.query(Order).all()]; print('=== production_tasks ==='); [print(f'  order={t.order_id} | event={t.event_id[:8]}...') for t in db.query(ProductionTask).all()]; print('=== event_logs ==='); [print(f'  {e.event_type} | {e.status}') for e in db.query(EventLog).all()]; db.close()"
```

### 7. 交互式 API 文档

浏览器打开：

```
http://127.0.0.1:8000/docs
```

可以直接在页面上点击 Try it out → Execute 来测试 API。

### 8. 运行测试

```bash
pip install pytest httpx
python -m pytest test_main.py -v
```

### 9. 清空数据库

**方法一：删除数据库文件（推荐，最快捷）**

先停止服务（Ctrl+C），然后执行：

```bash
del manufacturing.db manufacturing.db-wal manufacturing.db-shm
```

下次启动服务时会自动创建新的空数据库。

**方法二：用 Python 清空表数据（不删文件）**

```bash
python -c "from database import SessionLocal; from models import *; db=SessionLocal(); db.query(ProductionTask).delete(); db.query(EventLog).delete(); db.query(Order).delete(); db.commit(); print('数据库已清空'); db.close()"
```

> **注意**：清空顺序必须先删 ProductionTask 和 EventLog，再删 Order，因为存在外键关联。

### 10. 启动前端页面

```bash
pip install streamlit
streamlit run app.py --server.port 8501 --server.headless true
```

浏览器打开 http://localhost:8501 即可看到订单创建表单和事件流转链路。

> **前提**：FastAPI 后端必须在 8000 端口运行。

## 核心功能

### 1. 订单接入

接收外部模块的订单创建请求，将订单数据持久化到数据库，并立即返回受理结果，不阻塞调用方。

- 接口：`POST /orders`
- 请求参数：订单号、产品名称、数量
- 响应：202 Accepted，表示订单已受理，后台正在处理
- 幂等保护：相同订单号重复提交返回 409 Conflict

### 2. 自动触发生产任务

订单创建后，系统自动生成一条生产任务记录，关联到对应订单，无需人工介入。

- 触发条件：订单创建成功
- 产出：production_tasks 表新增一条记录，包含任务编号、关联订单号、产品信息
- 幂等保护：同一事件不会重复创建生产任务

### 3. 条件触发采购需求

当生产任务的数量超过阈值（>10）时，系统自动生成采购需求事件，记录物料名称和所需数量。

- 触发条件：生产任务数量 > 10
- 产出：采购需求日志（可扩展为采购建议表）
- 数量 ≤ 10 时仅记录日志，不触发采购

### 4. 库存校验与手动事务回滚

当 handler 检测到库存不足（quantity ≤ 0）时，抛出业务异常触发回滚。由于 Order 在 API 事务中已经 commit，handler 的 rollback 无法撤销它，因此采用**手动删除**的方式清理脏数据。

- 触发条件：quantity ≤ 0
- 回滚步骤：handler 抛异常 → dispatch rollback 撤销 handler 写入 → 标记 EventLog 为 failed → 手动 delete Order → commit
- 结果：数据库中无 Order、无 ProductionTask，EventLog 状态为 failed

**回滚原理：**

```
时间线：
  API 层:  Order + EventLog → commit → 202 返回     ← Order 已持久化
  后台:    handler 抛异常 → rollback                  ← 只能撤销 handler 内的写入
                                                          Order 在另一个事务里，rollback 管不到
           → 必须显式 delete Order → commit            ← 手动删除才能清理脏数据
```

**代码实现分布在三个位置：**

① handlers.py —— 检测异常并抛出：

```python
if event.quantity <= 0:
    raise ValueError("库存不足，无法创建生产任务")
```

② event_bus.py —— except 中 rollback + 标记 failed：

```python
except Exception as e:
    db.rollback()
    self._update_event_log_status(db, event.event_id, "failed")
    return
```

③ main.py —— dispatch 后检查状态，手动删除 Order：

```python
event_bus.dispatch(event, db)
log_entry = db.query(EventLog).filter(...).first()
if log_entry and log_entry.status == "failed":
    db.query(Order).filter(Order.order_id == event.order_id).delete()
    logger.info(f"手动回滚: 已删除订单 {event.order_id}")
db.commit()
```

### 5. 异常场景处理

系统支持三种异常场景的模拟与处理，每种异常都有明确提示，不会导致系统崩溃。

#### 超时模拟

- 触发方式：`product_name="SLOW"`
- 实现原理：handler 中 `time.sleep(5)` 模拟耗时操作，main.py 中设置 3 秒超时阈值，超时后 rollback + 标记 failed + 手动删除 Order
- 服务端提示：`ERROR:main:后台处理事件超时: elapsed=5.0s > timeout=3s, order_id=xxx, 订单生产采购失败`
- 前端提示：`❌ 订单生产采购失败`

#### 重复提交

- 触发方式：相同 order_id 再次 POST（可在创建订单表单中直接重复提交）
- 实现原理：API 层查询 Order 表，已存在则返回 409 并携带首次订单状态；事件总线层检查 EventLog 状态，completed 则幂等跳过
- API 返回：`409 {"detail": {"message": "order already exists", "order_id": "xxx", "status": "created"}}`
- 前端提示：`⚠️ 重复提交: 订单 xxx 已存在，首次订单状态: created`
- 服务端提示：`INFO:event_bus:事件已处理, 幂等跳过: event_id=xxx`

#### 网络失败模拟

- 触发方式：`product_name="NETFAIL"`
- 实现原理：handler 中调用不存在的库存服务（http://127.0.0.1:9999/inventory），requests 抛出 ConnectionError/Timeout，被 event_bus 的 try-except 捕获
- 服务端提示：`ERROR:main:后台处理事件失败: 网络服务不可用: HTTPConnectionPool...Max retries exceeded, 网络服务不可用，订单生产采购失败`
- 前端提示：`❌ 网络服务不可用，订单生产采购失败`

**三种异常统一处理链路：**

```
任何异常（超时/重复/网络失败）
        │
        ▼
event_bus.dispatch 的 try-except 捕获
        │
        ├── db.rollback()           ← 撤销 handler 写入
        ├── EventLog.status=failed  ← 标记失败
        └── main.py 检测到 failed
                │
                ├── 手动删除 Order  ← 清理脏数据
                └── 日志明确提示错误原因
```

### 6. 事件日志追踪

所有事件的处理过程均被记录到事件日志表中，支持事后审计与问题排查。

- 记录内容：事件ID、事件类型、完整事件数据（JSON）、处理状态
- 状态流转：pending → completed（成功）/ failed（失败）
- 可通过事件ID追溯任意一笔订单的完整处理链路

### 7. 健康检查

提供服务与数据库的连通性检测，供上层网关或监控系统调用。

- 接口：`GET /`
- 响应：`{"status": "ok", "db": "connected"}`

## 事件链路

```
外部模块调用 POST /orders
        │
        ▼
  订单写入数据库 + 事件日志写入（同一事务）
        │
        ▼ 返回 202 Accepted
        │
  后台异步处理（BackgroundTasks）
        │
        ▼
  OrderCreatedEvent ──→ 异常检测
        │
        ├── product_name="SLOW" ──→ 超时 → rollback → 手动删除 Order → failed
        │
        ├── product_name="NETFAIL" ──→ 网络失败 → rollback → 手动删除 Order → failed
        │
        ├── quantity ≤ 0 ──→ 库存不足 → rollback → 手动删除 Order → failed
        │
        └── 正常 ──→ 自动创建生产任务
                │
                ▼
        ProductionTaskCreatedEvent ──→ 判断数量
                │
                ├── 数量 > 10 ──→ PurchaseNeededEvent ──→ 记录采购需求
                │
                └── 数量 ≤ 10 ──→ 流程结束
```

## API 接口

### POST /orders — 创建订单

**请求体：**

```json
{
  "order_id": "ORD-001",
  "product_name": "Widget",
  "quantity": 5
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| order_id | string | 是 | 订单号，全局唯一 |
| product_name | string | 是 | 产品名称。特殊值：`SLOW`=模拟超时，`NETFAIL`=模拟网络失败 |
| quantity | integer | 是 | 订购数量，必须 > 0 |

**响应：**

| 状态码 | 含义 | 场景 |
|--------|------|------|
| 202 | 已受理 | 订单创建成功，后台自动处理中 |
| 409 | 冲突 | 订单号已存在（重复提交） |
| 500 | 服务器错误 | 内部异常 |

**202 响应体：**

```json
{
  "order_id": "ORD-001",
  "product_name": "Widget",
  "quantity": 5,
  "status": "pending processing"
}
```

### GET / — 健康检查

**响应体：**

```json
{
  "status": "ok",
  "db": "connected"
}
```

### GET /orders — 查询订单列表

**响应体：**

```json
{
  "orders": [
    {"order_id": "ORD-001", "product_name": "Widget", "quantity": 5, "status": "created", "created_at": "..."}
  ]
}
```

### GET /events — 查询事件日志

**响应体：**

```json
{
  "events": [
    {"event_id": "xxx", "event_type": "OrderCreatedEvent", "status": "completed", "order_id": "ORD-001", "created_at": "..."}
  ]
}
```

## 数据存储

数据库：SQLite（WAL 模式），文件名 `manufacturing.db`

### orders 表 — 订单

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| order_id | String | 订单号（唯一） |
| product_name | String | 产品名称 |
| quantity | Integer | 数量 |
| status | String | 状态，默认 "created" |
| created_at | DateTime | 创建时间（UTC） |

### production_tasks 表 — 生产任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| task_id | String | 任务编号（唯一） |
| order_id | String | 关联订单号 |
| product_name | String | 产品名称 |
| quantity | Integer | 数量 |
| status | String | 状态，默认 "pending" |
| event_id | String | 触发此任务的事件ID（唯一，幂等键） |
| created_at | DateTime | 创建时间（UTC） |

### event_logs 表 — 事件日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| event_id | String | 事件唯一ID（唯一） |
| event_type | String | 事件类型名 |
| payload | Text | 完整事件数据（JSON） |
| status | String | pending / completed / failed |
| created_at | DateTime | 创建时间（UTC） |

## 事件定义

三个核心业务事件均使用 Python dataclass 定义，每个事件包含唯一 event_id 和 UTC 时间戳。

| 事件 | 触发时机 | 携带信息 |
|------|---------|---------|
| OrderCreatedEvent | 订单创建成功 | 订单号、产品名称、数量 |
| ProductionTaskCreatedEvent | 生产任务创建成功 | 任务编号、订单号、产品名称、数量 |
| PurchaseNeededEvent | 生产数量超过阈值 | 采购编号、订单号、物料名称、需求数量 |

## 保障机制

| 机制 | 说明 |
|------|------|
| 事务一致性 | 订单写入与事件日志写入在同一数据库事务中，要么同时成功，要么同时回滚 |
| 手动事务回滚 | handler 失败时，rollback 撤销 handler 写入，手动删除已 commit 的 Order，确保无脏数据 |
| 幂等性 | 每个事件携带唯一 event_id，生产任务表通过 event_id 唯一索引防止重复创建 |
| 去重下单 | 订单号唯一索引，重复提交返回 409 |
| 异步处理 | 业务逻辑在 BackgroundTasks 中执行，API 立即返回，不阻塞调用方 |
| 失败可追溯 | 事件处理失败时日志状态标记为 failed，可通过 event_id 定位问题 |
| 库存校验 | quantity ≤ 0 时拒绝创建生产任务，触发回滚清理 |
| 超时保护 | 后台任务设置 3 秒超时阈值，超时自动回滚并删除脏数据 |
| 网络容错 | 外部服务调用失败时自动回滚，系统不崩溃 |
| 时区统一 | 所有时间字段使用 UTC，避免时区混乱 |

## 模块调用方式

本模块以 HTTP 服务形式运行，其他模块通过 RESTful API 调用，语言无关。

**Python 示例：**

```python
import requests

resp = requests.post("http://<服务地址>:8000/orders", json={
    "order_id": "ORD-001",
    "product_name": "Widget",
    "quantity": 15
})
print(resp.status_code)   # 202
print(resp.json())        # {"order_id": "ORD-001", ...}
```

**Java 示例：**

```java
HttpClient client = HttpClient.newHttpClient();
String body = "{\"order_id\":\"ORD-001\",\"product_name\":\"Widget\",\"quantity\":15}";
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://<服务地址>:8000/orders"))
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
```
