import time
from collections import defaultdict

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="事件驱动制造业协调", layout="wide")
st.title("🏭 事件驱动制造业协调系统")

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
            st.success(f"✅ 订单 {order_id} 已受理，后台处理中...")
            time.sleep(3)
            check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
            if check_resp.status_code == 200:
                orders = check_resp.json().get("orders", [])
                found = [o for o in orders if o["order_id"] == order_id]
                if found:
                    st.info(f"📋 订单状态: {found[0]['status']}")
                else:
                    st.error(f"❌ 订单生产采购失败")
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
                st.warning("⏱️ 超时订单已提交，handler 将等待5秒，3秒后触发超时回滚...")
                time.sleep(6)
                check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
                if check_resp.status_code == 200:
                    orders = check_resp.json().get("orders", [])
                    found = [o for o in orders if o["order_id"] == "ORD-TIMEOUT"]
                    if found:
                        st.info(f"📋 订单状态: {found[0]['status']}")
                    else:
                        st.error("❌ 订单生产采购失败")
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
                st.warning("🌐 网络失败订单已提交，handler 将调用不存在的库存服务...")
                time.sleep(4)
                check_resp = requests.get(f"{API_BASE}/orders", timeout=5)
                if check_resp.status_code == 200:
                    orders = check_resp.json().get("orders", [])
                    found = [o for o in orders if o["order_id"] == "ORD-NETFAIL"]
                    if found:
                        st.info(f"📋 订单状态: {found[0]['status']}")
                    else:
                        st.error("❌ 网络服务不可用，订单生产采购失败")
                st.rerun()
        except Exception as e:
            st.error(f"❌ 网络服务不可用，订单生产采购失败: {e}")

st.divider()

st.subheader("📦 订单列表")
try:
    resp = requests.get(f"{API_BASE}/orders", timeout=5)
    if resp.status_code == 200:
        orders = resp.json().get("orders", [])
        if orders:
            st.dataframe(
                orders,
                width="stretch",
                hide_index=True,
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
                with st.expander(f"📋 {oid}（{len(evts)} 个事件）", expanded=True):
                    cols = st.columns(len(evts))
                    for i, ev in enumerate(evts):
                        with cols[i]:
                            event_type = ev["event_type"]
                            status = ev["status"]
                            short_id = ev["event_id"][:8]

                            if status == "completed":
                                st.success(f"**{event_type}**")
                            elif status == "failed":
                                st.error(f"**{event_type}**")
                            else:
                                st.warning(f"**{event_type}**")

                            st.caption(f"ID: {short_id}...")
                            st.caption(f"状态: {status}")

                    chain_parts = []
                    for ev in evts:
                        icon = "✅" if ev["status"] == "completed" else "❌" if ev["status"] == "failed" else "⏳"
                        chain_parts.append(f"{icon} {ev['event_type']}")
                    st.markdown(" → ".join(chain_parts))
        else:
            st.info("暂无事件记录")
    else:
        st.error(f"获取事件失败: {resp.status_code}")
except Exception as e:
    st.error(f"连接服务失败: {e}")
