import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Chef Dashboard", page_icon="👨‍🍳", layout="wide")
st.title("👨‍🍳 Nova Coffee Shop - Chef Dashboard")

# ---- CSS Styles ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Rajdhani:wght@400;500&display=swap');

.stApp {
    background-color: #0a0a0f;
    color: #ffffff;
}

.order-card {
    background-color: #1a1a2e;
    border: 3px solid #ff6b35;
    border-radius: 15px;
    padding: 20px;
    margin: 15px 0;
}

.status-pending {
    color: #ff4444;
    font-weight: bold;
    font-size: 20px;
}

.status-preparing {
    color: #ffaa00;
    font-weight: bold;
    font-size: 20px;
}

.status-ready {
    color: #00ff88;
    font-weight: bold;
    font-size: 20px;
}

.total-orders {
    color: #ffaa00;
    font-weight: bold;
    font-size: 20px;
}

h1, h2, h3 {
    color: #ff6b35 !important;
    font-family: 'Orbitron', monospace !important;
}

body, p, div {
    font-family: 'Rajdhani', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ---- Initialize Firebase (only once) ----
if not firebase_admin._apps:
    cred = credentials.Certificate(os.getenv("FIREBASE_KEY_FILE"))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---- Fetch Orders from Firestore ----
try:
   docs = db.collection("orders").stream()
   orders = [{"doc_id": doc.id, **doc.to_dict()} for doc in docs]  # ✅ WITH doc_id!
except Exception as e:
    st.error(f"Firebase error {e}")
    order = []

# ---- Header ----
st.markdown(f"<p class='total-orders'>📋 Total Orders: {len(orders)}</p>", unsafe_allow_html=True)
st.subheader("Pending Orders")

if not orders:
    st.info("No orders right now. ☕")

# ---- Render Each Order ----
for order in orders:
    status = order.get("status", "pending")
    status_class = f"status-{status}"

    with st.container():
        st.markdown(f"""
        <div class="order-card">
            <h3>Order #{order.get('order_id', 'N/A')} — {order.get('name', 'Unknown')}</h3>
            <p>☕ <b>{order.get('size', '')} {order.get('coffee', '')}</b></p>
            <p>🪑 Table: {order.get('table', 'N/A')}</p>
            <p>Status: <span class="{status_class}">{status.upper()}</span></p>
        </div>
        """, unsafe_allow_html=True)

        cal1, cal2, cal3 = st.columns([1, 2, 3])

        with cal1:
            if st.button("👨‍🍳 Preparing", key=f"prep_{order['doc_id']}"):  # ✅ UNIQUE!
                db.collection("orders").document(order['doc_id']).update({"status": "preparing"})
                
        with cal2:
            time_mins = st.number_input(
                "Minutes:", min_value=1, value=5, key=f"time_{order['doc_id']}"
            )

        with cal3:
            if st.button("✅ Ready", key=f"ready_{order['doc_id']}"):  # ✅ UNIQUE!
                db.collection("orders").document(order['doc_id']).update({"status": "ready"})
                st.success(f"Order #{order.get('order_id')} is Ready!")
                st.rerun()

        st.divider()