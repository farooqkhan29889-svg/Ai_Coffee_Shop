from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import os
import streamlit as st
from langchain_groq import ChatGroq
from datetime import datetime, timedelta
from payment import calculate_bill, generate_bill_text
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage
import time

# ✅ ADD THIS TOO
import streamlit.components.v1 as components
components.html("""
    <script>
        window.scrollTo(0, 0);
    </script>
""", height=0)


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
            firebase_creds = dict(st.secrets["firebase"])
            if "private_key" in firebase_creds:
                firebase_creds["private_key"] = firebase_creds["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(firebase_creds)
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

if "pending_order" not in st.session_state:
    st.session_state.pending_order = None
    
if "order_start_time" not in st.session_state:
    st.session_state.order_start_time = None
    
if "table_number" not in st.session_state:
    table_param = st.query_params.get("table", "1")
    try:
        st.session_state.table_number = int(table_param)
    except:
        st.session_state.table_number = 1


#  ------ create chat histroy ----------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        SystemMessage(content=f"""You are NOVA, an AI waiter at Nova Coffee Shop, currently serving Table {st.session_state.table_number}.

*** LANGUAGE RULE - MUST FOLLOW ***

Selected language: {language}

YOU MUST RESPOND ONLY IN {language}.

NO PARENTHESES WITH ENGLISH TRANSLATION.
NO MIXING.
NO EXPLANATION IN OTHER LANGUAGE.

IF CUSTOMER SELECTED ENGLISH:
- Respond ONLY in English
- NO Hindi words
- NO translations
- Example: "Hello! What can I get for you?"

IF CUSTOMER SELECTED HINDI IN:
- Respond ONLY in Hindi
- NO English explanations
- NO translations in parentheses
- Example: "नमस्ते! आप क्या ऑर्डर करना चाहते हैं?"

NEVER DO THIS:
❌ "Namaste! Aapko kya chahiye? (Hello! What can I get for you?)"
❌ "Aap cappuccino (cappuccino) chahte hain?"
❌ "₹250 (two hundred fifty rupees)"

ALWAYS DO THIS:
✅ "नमस्ते! आप क्या चाहते हैं?"
✅ "आप कैपुचिनो चाहते हैं?"
✅ "₹250"

OR if English:
✅ "Hello! What can I get for you?"
✅ "You want cappuccino?"
✅ "₹250"

Our Coffee Menu:
- Cappuccino/कैपुचिनो: S:₹150 | M:₹200 | L:₹250
- Latte/लैट्टे: S:₹150 | M:₹200 | L:₹250
- Americano/अमेरिकानो: S:₹150 | M:₹200 | L:₹250
- Espresso/एस्प्रेसो: S:₹150 | M:₹200 | L:₹250
- Mocha/मोका: S:₹150 | M:₹200 | L:₹250
- Flat White/फ्लैट व्हाइट: S:₹150 | M:₹200 | L:₹250

IMPORTANT:
1. Ask for: Name → Coffee Type → Size (in selected language ONLY)
2. When complete, write:
   ORDER_CONFIRMED: [name] | [coffee] | [size]
3. NEVER mix languages
4. NEVER add explanations in other language
5. Be friendly but ONLY in selected language

Remember: {language} ONLY. NO MIXING.)

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
1. ALWAYS ask for: Name → Coffee Type → Size
2. NEVER confirm order without ALL 3 details
3. When complete, write EXACTLY:
   ORDER_CONFIRMED: [name] | [coffee] | [size] 

Example:
ORDER_CONFIRMED: Farooq | Cappuccino | Large | 3]

For SWEET orders:
STEP 1 do not take any order befor ask name and details of order 
like order name size and do not take any order withouth asking name and size of coffee
STEP 1 → Customer wants sweet
STEP 3 → Ask NAME first  
STEP 4 → Ask HOW MANY PIECES
STEP 5 → Confirm: ORDER_CONFIRMED: [name] | [sweet] | [pieces] pieces
like order name pieses and do not take any order withouth asking name and pieces of coffee

VERY IMPORTANT:
- Coffee → always ask SIZE
- Sweets → always ask PIECES not size
- NEVER confirm without name
- NEVER skip asking name

CONFIRMATION FORMAT — VERY STRICT:
After getting name and size — write ONE LINE like this:
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
            st.rerun()
    with col2:
        if st.button("🧾 Clear Orders", use_container_width=True):
           st.session_state.orders = []
           st.rerun

# ----- Header ----------
st.title("NOVA AI COFFEE SHOP")
st.caption("Next-Gen AI Assistant - Built by Farooq | Now taking coffee orders!")

# ✅ SHOW WHICH TABLE CUSTOMER IS AT
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.success(f"🪑 Table {st.session_state.table_number}")
st.markdown("---")

# ── PENDING ORDER TIMER ──
if st.session_state.pending_order:
    elapsed = (datetime.now() - st.session_state.order_start_time).total_seconds()
    remaining = 120 - elapsed
    
    if remaining > 0:
        st.warning(f"⏳ **Pending Order:** {st.session_state.pending_order['name']}'s {st.session_state.pending_order['size']} {st.session_state.pending_order['coffee']}")
        st.write(f"⏱️ **Auto-confirming in {int(remaining)} seconds...**")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✏️ Cancel / Change Order", use_container_width=True):
                st.session_state.pending_order = None
                st.session_state.order_start_time = None
                st.rerun()
        with c2:
            if st.button("✅ Confirm Now", use_container_width=True, type="primary"):
                st.session_state.pending_order["status"] = "confirmed"
                st.session_state.orders.append(st.session_state.pending_order)
                db.collection("orders").add(st.session_state.pending_order)
                st.session_state.pending_order = None
                st.session_state.order_start_time = None
                st.success("✅ Order confirmed successfully!")
                st.balloons()
                st.rerun()
        
        # Refresh every 1 second to update timer
        time.sleep(1)
        st.rerun()
    else:
        st.session_state.pending_order["status"] = "confirmed"
        st.session_state.orders.append(st.session_state.pending_order)
        db.collection("orders").add(st.session_state.pending_order)
        st.session_state.pending_order = None
        st.session_state.order_start_time = None
        st.success("✅ Order confirmed automatically!")
        st.balloons()
        st.rerun()
st.markdown("---")

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
    st.image("images/chocolate-cake.jpg", width=200)
    st.markdown("**Chocolate Cake** 🎂 → ₹150")
with col3:
    st.image("images/muffins.jpg", width=200)
    st.markdown("**Muffins** 🧁 → ₹140")

col4, col5, col6 = st.columns(3)
with col4:
    st.image("images/brownie.jpg", width=200)
    st.markdown("**Brownie** - 🍫 → ₹160")
with col5:
    st.image("images/gulab jamun.jpg", width=200)
    st.markdown("**Gulab Jamun** -  🍮 → ₹20")
with col6:
    st.image("images/ras malai.jpg", width=200)
    st.markdown("**Ras Mlai** - 🥟 → ₹15")
     
# ---- CHAT AREA ------
st.subheader("Chat With Nova 🤖")

for messeges in st.session_state.messeges:
    with st.chat_message(messeges["role"]):
        st.markdown(messeges["content"])

user_input = None

audio_value = st.audio_input("Or speak to Nova 🎤")

if audio_value is not None:
    import hashlib
    audio_bytes = audio_value.getvalue()
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    if "last_audio_hash" not in st.session_state or st.session_state.last_audio_hash != audio_hash:
        st.session_state.last_audio_hash = audio_hash
        with st.spinner("Listening... Transcribing your voice..."):
            from groq import Groq
            import os
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]
            groq_client = Groq(api_key=api_key)
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_bytes),
                model="whisper-large-v3",
                response_format="text"
            )
            # groq usually returns a string when response_format is "text", but just in case:
            user_input = transcription if isinstance(transcription, str) else getattr(transcription, 'text', str(transcription))

#  SINGLE chat input at top
text_input = st.chat_input("Ask Nova anything")
if text_input:
    user_input = text_input

if user_input:
    prompt = user_input
    
    # Step 1: Show user message
    st.session_state.messeges.append({"role":"user", "content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Step 2: Check if asking for bill
    if "bill" in prompt.lower() or "total bill" in prompt.lower():
        bill_data = calculate_bill(st.session_state.orders)
        
        if bill_data["total"] > 0:
            bill_text = generate_bill_text(bill_data, language)
            
            #  CORRECT: Use with statement
            with st.chat_message("assistant"):
                st.markdown(bill_text)
            
            #  PAYMENT OPTIONS
            st.divider()
            st.subheader("💳 Choose Payment Method")
            
        else:
            st.error("❌ No orders yet!")
    
    else:
        # Step 3: Normal chat flow (not asking for bill)
        st.session_state.chat_history.append(HumanMessage(content=prompt))
        response = llm.invoke(st.session_state.chat_history)
        ai_reply = response.content
        st.session_state.chat_history.append(AIMessage(content=ai_reply))
        
# ✅ SHOW AI RESPONSE
        with st.chat_message("assistant"):
            st.markdown(ai_reply)
            st.session_state.messeges.append({"role": "assistant", "content": ai_reply})
        
        # Check if order confirmed
        if "ORDER_CONFIRMED:" in ai_reply:
            parts = [p.strip() for p in ai_reply.split("ORDER_CONFIRMED:")[1].strip().split("|")]
            parts = [p for p in parts if p]
            if len(parts) >= 3:
                order = {
                    "order_id": len(st.session_state.orders) + 1,
                    "name": parts[0],
                    "table": st.session_state.table_number,
                    "coffee": parts[1],
                    "size": parts[2],
                    "time": datetime.now().strftime("%H:%M"),
                    "status": "pending"
                }
                st.session_state.temp_order = order
                bill_data = calculate_bill([order])
                bill_text = generate_bill_text(bill_data, language)
                with st.chat_message("assistant"):
                    st.markdown()
                # Step 4: REQUIRE payment (NEW!)
                st.divider()
                st.subheader("💳 Payment Required to Confirm Order")
                
                col1,col2,col3 = st.columns(3)
                with col1:
                    if st.button("💵 Cash on Counter", use_container_width=True):
                        order["payment_method"] = "Cash"
                        order["payment_status"] = "Pay at counter"
                        
                        # ONLY NOW add to orders!
                        st.session_state.orders.append(order)
                        db.collection("orders").add(order)
                        
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Order received!")
                        st.balloons()
                        st.rerun()
                
                with col2:
                    if st.button("📱 Pay with UPI", use_container_width=True):
                        st.info("🔄 Opening UPI payment gateway...")
                        # TODO: Integrate Razorpay UPI
                
                        order['payment_method'] = 'UPI'
                        order['payment_status'] = 'Paid'
                        st.session_state.orders.append(order)
                        db.collection("orders").add(order)
                
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Payment received!")
                        st.balloons()
                        st.rerun()
                     
                with col3:
                    if st.button("💳 Pay with CARD", use_container_width=True):
                        order["payment_method"] = "CARD"
                        order["payment_status"] = "Paid"
                        
                        # ONLY NOW ADD TO ORDERS
                        st.session_state.orders.append(order)
                        db.collection("orders").add(order)
                        
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Payment received!")
                        st.balloons()
                        st.rerun()
                st.warning("⚠️ Select a payment method to confirm order!")
            
    # ── ORDER FORM ──
# ── ORDER FORM ──
st.divider()
st.subheader("☕ Nova's Coffee Order")

with st.form("coffee_order", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
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
            "coffee": coffee_type,
            "size": size,
            "extras": extras if extras else [],
            "instructions": special_instructions if special_instructions else "None",
            "time": datetime.now().strftime("%H:%M"),
            "status": "pending"
        }
        st.session_state.pending_order = order
        st.session_state.order_start_time = datetime.now()
        
        st.info(f"⏳ Order #{order['order_id']} is pending. You have 2 minutes to change it!")
        st.rerun()
    elif submitted and not customer_name:
        st.error("Please enter your name before placing order")
# ----- CURRANT ORDER -------
if st.session_state.orders:
    st.divider()
    st.subheader(f"📋 Current Orders ({len(st.session_state.orders)})")
    for order in reversed(st.session_state.orders[-10:]):
        with st.container():
            col1,col2,col3 = st.columns([3,2,1])
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
else:
    st.info("No orders yet")
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
