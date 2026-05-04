import time
from collections import defaultdict

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="事件驱动制造业协调", layout="wide")
st.title("🏭 事件驱动制造业协调系统")

if "last_error" in st.session_state:
    st.error(st.session_state["last_error"])
    del st.session_state["last_error"]

if "last_success" in st.session_state:
    st.success(st.session_state["last_success"])
    del st.session_state["last_success"]

with st.form("create_order"):
    st.subheader("📝 创建订单")
    col1, col2, col3 = st.columns(3)
    with col1:
        order_id = st.text_input("订单号", value="ORD-001")
    with col2:
        product_name = st.text_input("产品名称", value="Widget")
    with col3:
        quantity = st.number_input("数量", value=5, step=1)
    submitted = st.form_submit_button("创建订单")

if submitted:
    try:
        resp = requests.post(f"{API_BASE}/orders", json={
            "order_id": order_id,
            "product_name": product_name,
            "quantity": quantity,
        }, timeout=5)
        if resp.status_code == 202:
            time.sleep(3)
            check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
            if check_resp.status_code == 200:
                orders = check_resp.json().get("orders", [])
                found = [o for o in orders if o["order_id"] == order_id]
                if found:
                    st.session_state["last_success"] = f"✅ 订单 {order_id} 已受理，状态: {found[0]['status']}"
                else:
                    st.session_state["last_error"] = f"❌ 订单 {order_id} 创建失败（库存不足/数量非法/产品不存在），事件链路中可查看失败记录"
            st.rerun()
        elif resp.status_code == 409:
            check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
            if check_resp.status_code == 200:
                orders = check_resp.json().get("orders", [])
                found = [o for o in orders if o["order_id"] == order_id]
                if found:
                    st.warning(f"⚠️ 重复提交: 订单 {order_id} 已存在，首次订单状态: {found[0]['status']}")
                else:
                    st.warning(f"⚠️ 重复提交: 订单 {order_id} 已存在")
            else:
                st.warning(f"⚠️ 重复提交: 订单 {order_id} 已存在")
        else:
            st.error(f"❌ 创建失败: {resp.status_code} {resp.text}")
    except Exception as e:
        st.error(f"❌ 网络服务不可用，订单生产采购失败: {e}")

st.divider()

st.subheader("🧪 异常场景模拟")
col_a, col_c = st.columns(2)

with col_a:
    if st.button("⏱️ 模拟超时", key="btn_timeout"):
        try:
            resp = requests.post(f"{API_BASE}/orders", json={
                "order_id": "ORD-TIMEOUT",
                "product_name": "SLOW",
                "quantity": 5,
            }, timeout=5)
            if resp.status_code == 202:
                time.sleep(6)
                check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
                if check_resp.status_code == 200:
                    orders = check_resp.json().get("orders", [])
                    found = [o for o in orders if o["order_id"] == "ORD-TIMEOUT"]
                    if found:
                        st.session_state["last_success"] = f"✅ 订单 ORD-TIMEOUT 已受理，状态: {found[0]['status']}"
                    else:
                        st.session_state["last_error"] = "❌ 订单 ORD-TIMEOUT 超时回滚，事件链路中可查看失败记录"
                st.rerun()
        except Exception as e:
            st.error(f"❌ 网络服务不可用，订单生产采购失败: {e}")

with col_c:
    if st.button("🌐 模拟网络失败", key="btn_netfail"):
        try:
            resp = requests.post(f"{API_BASE}/orders", json={
                "order_id": "ORD-NETFAIL",
                "product_name": "NETFAIL",
                "quantity": 5,
            }, timeout=5)
            if resp.status_code == 202:
                time.sleep(4)
                check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
                if check_resp.status_code == 200:
                    orders = check_resp.json().get("orders", [])
                    found = [o for o in orders if o["order_id"] == "ORD-NETFAIL"]
                    if found:
                        st.session_state["last_success"] = f"✅ 订单 ORD-NETFAIL 已受理，状态: {found[0]['status']}"
                    else:
                        st.session_state["last_error"] = "❌ 订单 ORD-NETFAIL 网络失败回滚，事件链路中可查看失败记录"
                st.rerun()
        except Exception as e:
            st.error(f"❌ 网络服务不可用，订单生产采购失败: {e}")

st.divider()

st.subheader("📦 库存信息")
try:
    resp = requests.get(f"{API_BASE}/inventory", timeout=5)
    if resp.status_code == 200:
        inventory = resp.json().get("inventory", [])
        if inventory:
            st.dataframe(
                inventory,
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("暂无库存记录")
    else:
        st.error(f"获取库存失败: {resp.status_code}")
except Exception as e:
    st.error(f"连接服务失败: {e}")

st.divider()

st.subheader("📦 订单列表")
try:
    resp = requests.get(f"{API_BASE}/orders", timeout=5)
    if resp.status_code == 200:
        orders = resp.json().get("orders", [])
        if orders:
            display_orders = []
            for o in orders:
                item = dict(o)
                if o.get("status") == "created":
                    item["状态图标"] = "✅"
                else:
                    item["状态图标"] = "⏳"
                display_orders.append(item)
            st.dataframe(
                display_orders,
                width="stretch",
                hide_index=True,
                column_order=["状态图标", "order_id", "product_name", "quantity", "status", "created_at"],
            )
        else:
            st.info("暂无订单")
    else:
        st.error(f"获取订单失败: {resp.status_code}")
except Exception as e:
    st.error(f"连接服务失败: {e}")

st.divider()

st.subheader("🔗 事件流转链路")
try:
    resp = requests.get(f"{API_BASE}/events", timeout=5)
    if resp.status_code == 200:
        events = resp.json().get("events", [])
        if events:
            grouped = defaultdict(list)
            for ev in events:
                oid = ev.get("order_id") or "未知订单"
                grouped[oid].append(ev)

            for oid, evts in grouped.items():
                completed = [ev for ev in evts if ev["status"] == "completed"]
                failed = [ev for ev in evts if ev["status"] == "failed"]
                pending = [ev for ev in evts if ev["status"] not in ("completed", "failed")]

                total = len(evts)
                parts = []
                if completed:
                    parts.append(f"✅ {len(completed)} 成功")
                if failed:
                    parts.append(f"❌ {len(failed)} 失败")
                if pending:
                    parts.append(f"⏳ {len(pending)} 处理中")
                summary = " | ".join(parts)

                with st.expander(f"📋 {oid}（{total} 个事件：{summary}）", expanded=True):
                    if completed:
                        st.markdown("**✅ 成功链路**")
                        cols = st.columns(len(completed))
                        for i, ev in enumerate(completed):
                            with cols[i]:
                                st.success(f"**{ev['event_type']}**")
                                st.caption(f"ID: {ev['event_id'][:8]}...")
                        chain_parts = [f"✅ {ev['event_type']}" for ev in completed]
                        st.markdown(" → ".join(chain_parts))

                    if failed:
                        with st.expander(f"❌ 失败尝试（{len(failed)} 次）", expanded=False):
                            for idx, ev in enumerate(failed, 1):
                                st.error(f"第 {idx} 次：**{ev['event_type']}** — 状态: failed | ID: {ev['event_id'][:8]}...")

                    if pending:
                        st.markdown("**⏳ 处理中**")
                        for ev in pending:
                            st.warning(f"**{ev['event_type']}** — 状态: pending | ID: {ev['event_id'][:8]}...")
        else:
            st.info("暂无事件记录")
    else:
        st.error(f"获取事件失败: {resp.status_code}")
except Exception as e:
    st.error(f"连接服务失败: {e}")
