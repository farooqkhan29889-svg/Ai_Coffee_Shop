import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

st.set_page_config(page_title="Chef Dashboard", page_icon=":material/restaurant_menu:", layout="wide", initial_sidebar_state="collapsed")
st.title("👨‍🍳 Nova Coffee Shop — Chef Dashboard")

# ---- CSS Styles ----
st.html("""
<style>
.stApp {
    background:
        radial-gradient(1100px 700px at 88% -5%, rgba(201,162,75,0.14), transparent 60%),
        radial-gradient(900px 650px at -5% 105%, rgba(201,162,75,0.10), transparent 55%),
        linear-gradient(165deg, #0f0e13 0%, #141218 50%, #0b0a0e 100%);
}
[data-testid="stHeader"] { background: transparent; }

.order-card {
    background: rgba(26, 24, 31, 0.7);
    border: 1px solid rgba(201, 162, 75, 0.25);
    border-radius: 18px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}

.status-pending {
    color: #ff6b6b;
    font-weight: bold;
    font-size: 20px;
}

.status-preparing {
    color: #ffb14d;
    font-weight: bold;
    font-size: 20px;
}

.status-ready {
    color: #5ee0a0;
    font-weight: bold;
    font-size: 20px;
}

.total-orders {
    color: #C9A24B;
    font-weight: bold;
    font-size: 20px;
}

h1, h2, h3 {
    background: linear-gradient(90deg, #F5E6C4, #C9A24B 55%, #F5E6C4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.stButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 999px;
    font-weight: 600;
}
</style>
""")

# ---- Initialize Firebase (only once) ----
if not firebase_admin._apps:
    try:
        key_path = os.getenv("FIREBASE_KEY_FILE")
        if key_path and os.path.exists(key_path):
            # 1. Local development (.env)
            cred = credentials.Certificate(key_path)
        else:
            # 2. Try Streamlit Secrets (for Cloud deployment)
            firebase_creds = dict(st.secrets["firebase"])
            if "private_key" in firebase_creds:
                firebase_creds["private_key"] = firebase_creds["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(firebase_creds)
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"⚠️ Failed to connect to Firebase: {e}")
        st.stop()

db = firestore.client()

# ---- Fetch Orders from Firestore ----
connected = True
try:
   docs = db.collection("orders").stream()
   orders = [{"doc_id": doc.id, **doc.to_dict()} for doc in docs]  # ✅ WITH doc_id!
except Exception as e:
    st.error(f"Firebase error {e}")
    orders = []
    connected = False

# Sort orders newest-first (using created_at, or order_id)
def get_order_sort_key(o):
    if "created_at" in o and o["created_at"]:
        return str(o["created_at"])
    return f"{o.get('order_id', 0):010d}" if isinstance(o.get('order_id'), int) else str(o.get('order_id', ''))

orders.sort(key=get_order_sort_key, reverse=True)

# ---- Auto-refresh so new customer orders appear live ----
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5000, key="chef_refresh")
except ImportError:
    pass

# ---- Connection status ----
with st.sidebar:
    if connected:
        st.badge("Live · Firebase synced", icon=":material/sensors:", color="green")
    else:
        st.badge("Offline", icon=":material/wifi_off:", color="red")

# ---- Header ----
st.markdown(f"<p class='total-orders'>📋 Total Orders: {len(orders)}</p>", unsafe_allow_html=True)
st.subheader("Pending Orders")

if not orders:
    st.info("No orders right now. ☕")

# ---- Render Each Order ----
for order in orders:
    status = order.get("status", "pending")
    status_class = f"status-{status}"

    if order.get("items") and isinstance(order["items"], list):
        items_html = ""
        for it in order["items"]:
            item_name = it.get("item", it.get("item_name", it.get("coffee", "")))
            size = it.get("size", "")
            size_str = f" ({size})" if size and size != "-" else ""
            items_html += f"<p>☕ <b>{item_name}</b>{size_str}</p>"
    else:
        items_html = f"<p>☕ <b>{order.get('size', '')} {order.get('coffee', '')}</b></p>"

    pay_method = order.get("payment_method", "N/A")
    pay_status = order.get("payment_status", "Unpaid")
    pay_badge = f"{pay_method} ({pay_status})" if pay_method != "N/A" else pay_status

    est = order.get("estimated_time")
    est_html = f"<p>⏱️ Est. waiting: <b>{est} min</b></p>" if est else ""
    prep_at = order.get("preparing_at")
    prep_html = f"<p>🔥 Started: {prep_at[:19].replace('T', ' ')}</p>" if prep_at else ""

    with st.container():
        st.markdown(f"""
        <div class="order-card">
            <h3>Order #{order.get('order_id', 'N/A')} — {order.get('name', 'Unknown')}</h3>
            {items_html}
            <p>🪑 Table: {order.get('table', 'N/A')}</p>
            <p>💳 Payment: <b>{pay_badge}</b></p>
            <p>Status: <span class="{status_class}">{status.upper()}</span></p>
            {est_html}
            {prep_html}
        </div>
        """, unsafe_allow_html=True)

        cal1, cal2, cal3 = st.columns([1, 2, 3])

        with cal2:
            quick1, quick2 = st.columns(2)
            with quick1:
                if st.button("⏱️ 10 min", key=f"t10_{order['doc_id']}", use_container_width=True):
                    db.collection("orders").document(order['doc_id']).update({
                        "status": "preparing",
                        "estimated_time": 10,
                        "preparing_at": datetime.now().isoformat()
                    })
                    st.rerun()
            with quick2:
                if st.button("⏱️ 15 min", key=f"t15_{order['doc_id']}", use_container_width=True):
                    db.collection("orders").document(order['doc_id']).update({
                        "status": "preparing",
                        "estimated_time": 15,
                        "preparing_at": datetime.now().isoformat()
                    })
                    st.rerun()
            time_mins = st.number_input(
                "Custom minutes:", min_value=1, value=5, key=f"time_{order['doc_id']}"
            )

        with cal1:
            if st.button("👨‍🍳 Preparing", key=f"prep_{order['doc_id']}"):  # ✅ UNIQUE!
                db.collection("orders").document(order['doc_id']).update({
                    "status": "preparing",
                    "estimated_time": time_mins,
                    "preparing_at": datetime.now().isoformat()
                })
                st.rerun()

        with cal3:
            if st.button("✅ Ready", key=f"ready_{order['doc_id']}"):  # ✅ UNIQUE!
                db.collection("orders").document(order['doc_id']).update({
                    "status": "ready",
                    "ready_at": datetime.now().isoformat()
                })
                st.success(f"Order #{order.get('order_id')} is Ready!")
                st.rerun()

        st.divider()