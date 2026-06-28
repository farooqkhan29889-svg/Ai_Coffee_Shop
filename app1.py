from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import os
import streamlit as st
from langchain_groq import ChatGroq
from datetime import datetime
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage

load_dotenv()
st.set_page_config(page_title="Nova Coffee", page_icon="☕", layout="wide")

# Add this after your title
st.subheader("🌐Select Language / भाषा चुनें")
language = st.radio(
        "",
    ["Hindi IN", "English GS"],
    horizontal=True
)
# Initialize Firebase safely for Streamlit
if not firebase_admin._apps:
    try:
        # 1. Try Streamlit Secrets (for Cloud deployment)
        if "firebase" in st.secrets:
            # Convert Streamlit secrets to dict for Firebase
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
        # 2. Fallback to local .env file (for local development)
        else:
            key_path = os.getenv("FIREBASE_KEY_FILE")
            if not key_path:
                st.error("⚠️ Could not find Firebase credentials in st.secrets or .env!")
                st.stop()
            cred = credentials.Certificate(key_path)
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"⚠️ Failed to connect to Firebase: {e}")
        st.stop()

db = firestore.client()

# ── SESSION STATE — must be at top before everything ──
if "messeges" not in st.session_state:
    st.session_state.messeges = []
    
if "orders" not in st.session_state:
    st.session_state.orders = []
    
if "table_number" not in st.session_state:
    st.session_state.table_number = 1
# ── GET ORDERS FROM FIREBASE (with caching) ──

#  ------ create chat histroy ----------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        SystemMessage(content="""You are NOVA, an AI waiter at Nova Coffee Shop.

LANGUAGE RULE — VERY STRICT:
- Customer selected English → reply 100%  in English ALWAYS
- Customer selected Hindi → reply 100%  in Hindi ALWAYS
- NEVER use mix Hindi and Enlish whan you reply only give answer in selected language
- NEVER mix Hindi and English in same reply
- CLEAR speek hindi give properly answer in hindi
- NEVER switch language mid conversation
- Check selected language at top of page — follow it strictly
- Even if customer writes in different language — reply in SELECTED language only

Our Coffee Menu:
- Latte ☕ → S:₹150 | M:₹200 | L:₹250
- Americano ☕ → S:₹150 | M:₹200 | L:₹250
- Cappuccino ☕ → S:₹150 | M:₹200 | L:₹250
- Espresso ☕ → S:₹150 | M:₹200 | L:₹250
- Mocha ☕ → S:₹150 | M:₹200 | L:₹250
- Flat White ☕ → S:₹150 | M:₹200 | L:₹250

Our Sweets Menu:
- Cookies 🍪 → ₹100
- Chocolate Cake 🎂 → ₹150
- Muffins 🧁 → ₹140
- Brownie 🍫 → ₹160
- Gulab Jamun 🍮 → ₹20
- Ras Mlai 🥟 → ₹30

SMPORTANT RULES:
1. ALWAYS ask for: Name → Coffee Type → Size → Table Number
2. NEVER confirm order without ALL 4 details
3. When complete, write EXACTLY:
   ORDER_CONFIRMED: [name] | [coffee] | [size] | [table]

Example:
ORDER_CONFIRMED: Farooq | Cappuccino | Large | 3]

For SWEET orders:
STEP 1 do not take any order befor ask name and details of order 
like order name size and also tble number
STEP 1 → Customer wants sweet
STEP 3 → Ask NAME first  
STEP 4 → Ask HOW MANY PIECES
STEP 5 → Confirm: ORDER_CONFIRMED: [name] | [sweet] | [pieces] pieces


VERY IMPORTANT:
- Coffee → always ask SIZE
- Sweets → always ask PIECES not size
- NEVER confirm without name
- NEVER skip asking name
- NEVER taking order without asking table number name size 

CONFIRMATION FORMAT — VERY STRICT:
After getting table number and name and size — write ONE LINE like this:
ORDER_CONFIRMED: [name] | [item] | [size/pieces]

For multiple items write multiple lines:
ORDER_CONFIRMED: Farooq | Cappuccino | Large
ORDER_CONFIRMED: Farooq | Samosa | 5 pieces
ORDER_CONFIRMED: Farooq | Gulab Jamun | 5 pieces

NEVER use bullet points for ORDER_CONFIRMED
NEVER use * or - before ORDER_CONFIRMED
ALWAYS write ORDER_CONFIRMED on its own line
ALWAYS use | to separate name, item, size

Be friendly and warm like a real waiter!""")
    ]
    
# ---- llm -----

@st.cache_resource
def load_llm():
    return ChatGroq(model="llama-3.1-8b-instant",temperature=0.3)
llm = load_llm()

# ── CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Rajdhani:wght@400;500&display=swap');

.stApp {
    background-color: #0a0a0f;
    color: #ffffff;
}

[data-testid="stSidebar"] {
    background-color: #0d0d1a;
    border-right: 1px solid #333;
}

h1, h2, h3 {
    color: #ff6b35 !important;
    font-family: 'Orbitron', monospace !important;
}

[data-testid="stChatMessage"] {
    background-color: #00ffcc !important;
    border: 1px solid #333;
    border-radius: 15px;
}
[data-testid="stChatMessage"] p {
    font-weight: bold !important;
    font-size: 16px !important;
}
[data-testid="stChatInput"] textarea {
    background-color: #e74c3c !important;
    color: white !important;
    border: 1px solid #ff6b3544 !important;
}
[data-testid="stChatInput"] p {
    font-weight: bold !important;
    font-size: 20px !important;
}
</style>
""", unsafe_allow_html=True)

# ----- siderbar -----
with st.sidebar:
    st.subheader("Nova Settings")
    ai_model = st.selectbox("AI Model", ["llama-3.1-8b-instant", "mixtral-8x7b-32768"])
    tempretur = st.slider("Temperature", 0.0, 1.0, 0.70, 0.05)
    st.divider()
    st.metric("Chat Messages", len(st.session_state.messeges))
    st.metric("Coffee Orders", len(st.session_state.orders))
    st.divider()
    now = datetime.now()
    st.write(f"📅 Date: {now.strftime('%d %b %Y')}")
    st.write(f"⏰ Time: {now.strftime('%I:%M %p')}")
    st.divider()
    col1,col2 = st.columns(2)
    with col1:
       if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messeges = []
            st.session_state.chat_history = [st.session_state.chat_history[0]]
            st.rerun
    with col2:
        if st.button("🧾 Clear Orders", use_container_width=True):
           st.session_state.orders = []
           st.rerun

# ----- Header ----------
st.title("NOVA AI COFFEE SHOP")
st.caption("Next-Gen AI Assistant - Built by Farooq | Now taking coffee orders!")
st.image("images/coffee.jpg", caption="☕ Fresh Brewed Coffee Every Day", use_container_width=True)
            
# ── MENU IMAGES ──
st.subheader("Our Coffee Menu ☕")
col1, col2, col3 = st.columns(3)
with col1:
    st.image("images/cappuccino.jpg", width=200)
    st.markdown("**Cappuccino** - S:₹150 | M:₹200 | L:₹250")
with col2:
    st.image("images/latte.jpg", width=200)
    st.markdown("**Latte** - S:₹150 | M:₹200 | L:₹250")
with col3:
    st.image("images/black coffee.jpg", width=200)
    st.markdown("**Black coffee** - S:₹150 | M:₹200 | L:₹250")

col4, col5, col6 = st.columns(3)
with col4:
    st.image("images/espresso.jpg", width=200)
    st.markdown("**Espresso** - S:₹150 | M:₹200 | L:₹250")
with col5:
    st.image("images/americano.jpg", width=200)
    st.markdown("**Americano** - S:₹150 | M:₹200 | L:₹250")
with col6:
    st.image("images/flat-white.jpg", width=200)
    st.markdown("**Flat White** - S:₹150 | M:₹200 | L:₹250")
    
# ── MENU IMAGES ──
st.subheader("Our Sweets Menu 🍵")
col1, col2, col3 = st.columns(3)
with col1:
    st.image("images/cookies.jpg", width=200)
    st.markdown("**Cookies** - ₹100")
with col2:
    st.image("images/Chocolate Cake.jpg", width=200)
    st.markdown("**Chocolate Cake** 🎂 → ₹150")
with col3:
    st.image("images/Muffins.jpg", width=200)
    st.markdown("**Muffins** 🧁 → ₹140")

col4, col5, col6 = st.columns(3)
with col4:
    st.image("images/Brownie chocplat.jpg", width=200)
    st.markdown("**Brownie chocplat** - 🍫 → ₹160")
with col5:
    st.image("images/Gulab Jamun.jpg", width=200)
    st.markdown("**Gulab Jamun** -  🍮 → ₹20")
with col6:
    st.image("images/Ras Mlai.jpg", width=200)
    st.markdown("**Ras Mlai** - 🥟 → ₹15")
     
# ---- CHAT AREA ------
st.subheader("Chat With Nova 🤖")

for messeges in st.session_state.messeges:
    with st.chat_message(messeges["role"]):
        st.markdown(messeges["content"])

if prompt := st.chat_input("Ask Nova anything"):
    # --- SHOW USER MESSEGE ---
    st.session_state.messeges.append({"role":"user", "content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Get AI response
    st.session_state.chat_history.append(HumanMessage(content=prompt))
    response = llm.invoke(st.session_state.chat_history)
    ai_reply = response.content
    st.session_state.chat_history.append(AIMessage(content=ai_reply))
    
    # Check if order confirmed
    if "ORDER_CONFIRMED:" in ai_reply:
        parts = [p.strip() for p in ai_reply.split("ORDER_CONFIRMED:")[1].strip().split("|")]
        parts = [p for p in parts if p]  # Remove empty parts
        if len(parts) >= 3:  # At least 3 parts
            order = {
                "order_id": len(st.session_state.orders) + 1,
                "name": parts[0],
                "table": st.session_state.table_number,
                "coffee": parts[1],
                "size": parts[2],
                "extras": [],
                "instructions": "None",
                "time": datetime.now().strftime("%H:%M"),
                "status": "confirmed"
            }
        st.session_state.orders.append(order)
        db.collection("orders").add(order)  # ✅ NEW 
        st.success(f"✅ Order #{order['order_id']} confirmed for {order['name']}! ☕")
        st.balloons()
            
    # --- SHOW AI RIPLY ----
    with st.chat_message("assistant"):
        st.markdown(ai_reply)
        st.session_state.messeges.append({"role": "assistant", "content": ai_reply})
    
    # ── ORDER FORM ──
st.divider()
st.subheader("☕ Nova's Coffee Order")

with st.form("coffee_order", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        table_number = st.selectbox("🪑 Table Number", range(1, 11))
        st.session_state.table_number = table_number  # ← ADD THIS LINE!
        customer_name = st.text_input("📝 Your name", placeholder="Enter your name")
        coffee_type = st.selectbox("☕ Coffee type", ["Latte", "Americano", "Cappuccino", "Espresso", "Mocha", "Flat White"])
    with col2:
        size = st.radio("📏 Size", ["Small", "Medium", "Large"], horizontal=True)
        extras = st.multiselect("➕ Extras", ["Extra shot", "Vanilla syrup", "Caramel syrup", "Oat milk", "Whipped cream"])
        special_instructions = st.text_area("📝 Special instructions (optional)")
        submitted = st.form_submit_button("✅ Place Order", use_container_width=True, type="primary")
    
    if submitted and customer_name:
        order = {
            "order_id": len(st.session_state.orders) + 1,
            "name": customer_name,
            "table": st.session_state.table_number,
            "coffee": coffee_type,
            "size": size,
            "extras": extras if extras else [],
            "instructions": special_instructions if special_instructions else "None",
            "time": datetime.now().strftime("%H:%M"),
            "status": "confirmed"
        }
        st.session_state.orders.append(order)
        db.collection("orders").add(order)  # ✅ NEW
        st.success(f"✅ Order...")      
        st.success(f"✅ Order #{order['order_id']} confirmed, {customer_name}!")
        extras_text = ", ".join(extras) if extras else "No extras"
        st.info(f"☕ {size} {coffee_type} | ➕ {extras_text} | ⏱️ Ready in 5-7 minutes")
        st.balloons()
        st.rerun()
    elif submitted and not customer_name:
        st.error("Please enter your name before placing order")
# ── CURRENT ORDERS ──
if st.session_state.orders:
    st.divider()
    st.subheader(f"📋 Current Orders ({len(st.session_state.orders)})")
    for order in reversed(st.session_state.orders[-10:]):
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**#{order['order_id']} - {order['name']}**")
                st.write(f"☕ {order['size']} {order['coffee']}")
            with col2:
                st.write(f"⏱️ Time: {order['time']}")
                st.write(f"📌 Status: ✅ {order['status']}")
            with col3:
                if st.button(f"✅ Done", key=f"done_{order['order_id']}"):
                    order['status'] = "completed"
                    st.rerun()
            st.divider()
# ── ANALYTICS ──
if len(st.session_state.orders) > 0:
    st.divider()
    with st.expander("📊 Today's Analytics"):
        coffee_counts = {}
        for order in st.session_state.orders:
            coffee = order['coffee']
            coffee_counts[coffee] = coffee_counts.get(coffee, 0) + 1
        st.write("**Popular coffees today:**")
        for coffee, count in sorted(coffee_counts.items(), key=lambda x: x[1], reverse=True):
            st.write(f"- {coffee}: {count} order(s)")
        prices = {"Small": 150, "Medium": 200, "Large": 250}
        total_revenue = sum(prices.get(order['size'], 0) for order in st.session_state.orders)
        st.metric("💰 Estimated Revenue", f"₹{total_revenue}")

# ── FOOTER ──
st.divider()
st.caption("🤖 Nova AI Coffee Assistant | Built with ❤️ by Farooq | © 2026")