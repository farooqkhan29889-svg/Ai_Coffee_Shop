from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import os
import streamlit as st
from langchain_groq import ChatGroq
from datetime import datetime, timedelta
from payment import calculate_bill, generate_bill_text, applied_offer, PRICES, FOOD_PRICES
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage
import re

# ✅ ADD THIS TOO
import streamlit.components.v1 as components
components.html("""
    <script>
        window.scrollTo(0, 0);
    </script>
""", height=0)


load_dotenv()
st.set_page_config(page_title="Nova Coffee", page_icon=":material/local_cafe:", layout="wide", initial_sidebar_state="collapsed")

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

if "cart" not in st.session_state:
    st.session_state.cart = []

if "show_receipt_for" not in st.session_state:
    st.session_state.show_receipt_for = None

if "ready_notified" not in st.session_state:
    st.session_state.ready_notified = set()

if "orders_loaded_from_db" not in st.session_state:
    st.session_state.orders_loaded_from_db = False

if "table_number" not in st.session_state:
    table_param = st.query_params.get("table", "1")
    try:
        st.session_state.table_number = int(table_param)
    except:
        st.session_state.table_number = 1

# ---- Unique order number (shared counter in Firebase) ----
def next_order_number():
    try:
        txn = db.transaction()

        def _increment(transaction):
            doc_ref = db.collection("meta").document("order_counter")
            snap = doc_ref.get(transaction=transaction)
            current = snap.get("value") if snap.exists else 1000
            transaction.set(doc_ref, {"value": current + 1})
            return current

        return txn.transaction(_increment)
    except Exception:
        return int(datetime.now().strftime("%H%M%S"))

# ---- Look up price for chat-ordered items ----
def item_price(item_name, size):
    size = size or ""
    if item_name in PRICES and size in PRICES[item_name]:
        return PRICES[item_name][size]
    if item_name in FOOD_PRICES:
        qty = 1
        nums = re.findall(r"\d+", size)
        if nums:
            qty = int(nums[0])
        return FOOD_PRICES[item_name] * qty
    return 0

# ---- Reload this table's orders from Firebase (survives page refresh) ----
if not st.session_state.orders_loaded_from_db:
    st.session_state.orders_loaded_from_db = True
    try:
        docs = db.collection("orders").where("table", "==", st.session_state.table_number).stream()
        for doc in docs:
            data = doc.to_dict()
            if "doc_id" not in data:
                data["doc_id"] = doc.id
            if not any(o.get("doc_id") == doc.id for o in st.session_state.orders):
                st.session_state.orders.append(data)
            if data.get("status") == "ready":
                st.session_state.ready_notified.add(data.get("doc_id") or data.get("order_id"))
    except Exception:
        pass


#  ------ create chat histroy ----------

def build_system_message(language, table_number):
    return SystemMessage(content=f"""You are NOVA, an AI waiter at Nova Coffee Shop, currently serving Table {table_number}.

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
- Cappuccino/कैपुचिनो: S:₹150 | L:₹250
- Latte/लैट्टे: S:₹150 | L:₹250
- Americano/अमेरिकानो: S:₹150 | L:₹250
- Espresso/एस्प्रेसो: S:₹150 | L:₹250
- Mocha/मोका: S:₹150 | L:₹250
- Flat White/फ्लैट व्हाइट: S:₹150 | L:₹250

IMPORTANT:
1. Ask for: Name → Coffee Type → Size (in selected language ONLY)
2. When complete, write:
   ORDER_CONFIRMED: [name] | [coffee] | [size]
3. NEVER mix languages
4. NEVER add explanations in other language
5. Be friendly but ONLY in selected language

Remember: {language} ONLY. NO MIXING.)

Our Coffee Menu:
- Latte ☕ → S:₹150 | L:₹250
- Americano ☕ → S:₹150 | L:₹250
- Cappuccino ☕ → S:₹150 | L:₹250
- Espresso ☕ → S:₹150 | L:₹250
- Mocha ☕ → S:₹150 | L:₹250
- Flat White ☕ → S:₹150 | L:₹250

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

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [build_system_message(language, st.session_state.table_number)]

if "applied_language" not in st.session_state:
    st.session_state.applied_language = language

if st.session_state.applied_language != language:
    st.session_state.applied_language = language
    st.session_state.chat_history[0] = build_system_message(language, st.session_state.table_number)
    st.toast(f"🌐 Language switched to {language}")
    
# ---- llm -----

@st.cache_resource
def load_llm():
    return ChatGroq(model="llama-3.1-8b-instant",temperature=0.3)
llm = load_llm()

# ── CSS ──
st.html("""
<style>
.stApp {
    background:
        radial-gradient(1100px 700px at 88% -5%, rgba(201,162,75,0.14), transparent 60%),
        radial-gradient(900px 650px at -5% 105%, rgba(201,162,75,0.10), transparent 55%),
        linear-gradient(165deg, #0f0e13 0%, #141218 50%, #0b0a0e 100%);
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

h1, h2, h3 {
    background: linear-gradient(90deg, #F5E6C4, #C9A24B 55%, #F5E6C4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #141218 0%, #100e13 100%);
    border-right: 1px solid rgba(201,162,75,0.15);
}

[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 12px 16px;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: rgba(201,162,75,0.12);
    border: 1px solid rgba(201,162,75,0.25);
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.09);
}

.stButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 999px;
    font-weight: 600;
    transition: transform .15s ease, box-shadow .15s ease;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(201,162,75,0.25);
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px;
    border-color: rgba(201,162,75,0.18) !important;
}
</style>
""")

# ----- siderbar -----
with st.sidebar:
    st.subheader(":material/tune: Nova Settings")
    ai_model = st.selectbox("AI Model", ["llama-3.1-8b-instant", "mixtral-8x7b-32768"])
    tempretur = st.slider("Temperature", 0.0, 1.0, 0.70, 0.05)
    st.space("small")
    st.metric("Chat Messages", len(st.session_state.messeges))
    st.metric("Coffee Orders And Sweets", len(st.session_state.orders))
    now = datetime.now()
    st.caption(f":material/calendar_today: {now.strftime('%d %b %Y')}  •  {now.strftime('%I:%M %p')}")
    st.space("medium")
    col1,col2 = st.columns(2)
    with col1:
       if st.button(":material/delete_sweep: Clear chat", width="stretch"):
            st.session_state.messeges = []
            st.session_state.chat_history = [st.session_state.chat_history[0]]
            st.rerun()
    with col2:
        if st.button(":material/delete: Clear orders", width="stretch"):
           st.session_state.orders = []
           st.rerun()

# ----- Header ----------
with st.container(horizontal_alignment="center"):
    st.title("NOVA AI COFFEE SHOP")
    st.image("images/coffee.jpg", width="stretch")
    st.caption("Premium AI Coffee Shop — order by chat, tap, or voice")
    st.badge(f"Table {st.session_state.table_number}", icon=":material/table_restaurant:", color="orange")

st.markdown("---")

def add_to_cart(item, size, price):
    st.session_state.cart.append({"item": item, "size": size, "price": price})
    st.toast(f"✨ Added {item} to cart!", icon="🛒")

def menu_card(image_path, name, price_text, size_buttons):
    with st.container(border=True):
        st.image(image_path, width="stretch")
        st.markdown(f"**{name}**", text_alignment="center")
        if price_text:
            st.caption(price_text, text_alignment="center")
        cols = st.columns(len(size_buttons))
        for col, (label, key, size, price) in zip(cols, size_buttons):
            with col:
                st.button(label, key=key, on_click=add_to_cart,
                          args=(name, size, price), width="stretch")

@st.dialog("🧾 Order receipt")
def show_receipt(order):
    import random
    order_num = f"#{random.randint(1000, 9999)}"
    st.markdown(f"### Thank you, {order['name']}!", text_alignment="center")
    st.caption(f"Receipt: {order_num} · Order #{order['order_id']} · {order.get('time', '')}", text_alignment="center")
    st.space("small")
    st.markdown("**Items ordered:**")
    if order.get("items"):
        for sub_item in order["items"]:
            size_str = f" ({sub_item['size']})" if sub_item.get('size') and sub_item.get('size') != "-" else ""
            st.write(f"- {sub_item.get('item', sub_item.get('item_name'))}{size_str}")
    else:
        st.write(f"- {order.get('size', '')} {order.get('coffee', '')}")
    st.divider()
    if order.get("discount"):
        st.write(f"🎟️ Coupon: {order.get('coupon_code', '')} (-₹{order['discount']})")
        st.markdown(f"### Final Total: ₹{order.get('final_total', 0)}")
    st.markdown("We hope you enjoy your order! ❤️", text_alignment="center")
    if st.button(":material/close: Close", width="stretch"):
        st.session_state.show_receipt_for = None
        st.rerun()

if st.session_state.show_receipt_for:
    show_receipt(st.session_state.show_receipt_for)

# ── MENU ──
st.subheader(":material/local_cafe: Our coffee menu")
col1, col2, col3 = st.columns(3)
with col1:
    menu_card("images/cappuccino.jpg", "Cappuccino", "Small ₹150 · Large ₹250",
              [("S ₹150", "cap_s", "Small", 150), ("L ₹250", "cap_l", "Large", 250)])
with col2:
    menu_card("images/latte.jpg", "Latte", "Small ₹150 · Large ₹250",
              [("S ₹150", "lat_s", "Small", 150), ("L ₹250", "lat_l", "Large", 250)])
with col3:
    menu_card("images/black coffee.jpg", "Black Coffee", "Small ₹150 · Large ₹250",
              [("S ₹150", "blk_s", "Small", 150), ("L ₹250", "blk_l", "Large", 250)])

col4, col5, col6 = st.columns(3)
with col4:
    menu_card("images/espresso.jpg", "Espresso", "Small ₹150 · Large ₹250",
              [("S ₹150", "esp_s", "Small", 150), ("L ₹250", "esp_l", "Large", 250)])
with col5:
    menu_card("images/americano.jpg", "Americano", "Small ₹150 · Large ₹250",
              [("S ₹150", "amr_s", "Small", 150), ("L ₹250", "amr_l", "Large", 250)])
with col6:
    menu_card("images/flat-white.jpg", "Flat White", "Small ₹150 · Large ₹250",
              [("S ₹150", "flt_s", "Small", 150), ("L ₹250", "flt_l", "Large", 250)])

st.subheader(":material/icecream: Our sweets menu")
col1, col2, col3 = st.columns(3)
with col1:
    menu_card("images/cookies.jpg", "Cookies", "₹100",
              [("Add", "cookie", "-", 100)])
with col2:
    menu_card("images/chocolate-cake.jpg", "Chocolate Cake", "₹150",
              [("Add", "cake", "-", 150)])
with col3:
    menu_card("images/muffins.jpg", "Muffins", "₹140",
              [("Add", "muffin", "-", 140)])

col4, col5, col6 = st.columns(3)
with col4:
    menu_card("images/brownie.jpg", "Brownie", "₹160",
              [("Add", "brownie", "-", 160)])
with col5:
    menu_card("images/gulab jamun.jpg", "Gulab Jamun", "₹20",
              [("Add", "gulab", "-", 20)])
with col6:
    menu_card("images/ras malai.jpg", "Ras Mlai", "₹15",
              [("Add", "rasmalai", "-", 15)])

# ---- CHAT AREA ------
st.subheader(":material/support_agent: Chat with Nova")

for messeges in st.session_state.messeges:
    with st.chat_message(messeges["role"]):
        st.markdown(messeges["content"])

user_input = None

audio_value = st.audio_input("Or speak to Nova")

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
            st.subheader(":material/payments: Choose payment method")
            
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
            lines = [line.strip() for line in ai_reply.splitlines() if "ORDER_CONFIRMED:" in line]
            order_items = []
            customer_name = "Customer"
            for line in lines:
                parts = [p.strip() for p in line.split("ORDER_CONFIRMED:")[1].strip().split("|")]
                parts = [p for p in parts if p]
                if len(parts) >= 3:
                    customer_name = parts[0]
                    order_items.append({
                        "item": parts[1],
                        "size": parts[2],
                        "price": item_price(parts[1], parts[2])
                    })
            if order_items:
                primary_coffee = ", ".join([it["item"] for it in order_items])
                order = {
                    "order_id": next_order_number(),
                    "name": customer_name,
                    "table": st.session_state.table_number,
                    "coffee": primary_coffee,
                    "size": order_items[0]["size"] if len(order_items) == 1 else "",
                    "items": order_items,
                    "time": datetime.now().strftime("%H:%M"),
                    "created_at": datetime.now().isoformat(),
                    "status": "pending"
                }
                bill_data = calculate_bill([order])
                bill_text = generate_bill_text(bill_data, language)
                with st.chat_message("assistant"):
                    st.markdown(bill_text)
                # Step 4: REQUIRE payment (NEW!)
                st.divider()
                st.subheader(":material/payments: Payment required to confirm order")

                col1,col2,col3 = st.columns(3)
                with col1:
                    if st.button(":material/point_of_sale: Cash on counter", width="stretch"):
                        order["payment_method"] = "Cash"
                        order["payment_status"] = "Pay at counter"
                        
                        # ONLY NOW add to orders!
                        _, doc_ref = db.collection("orders").add(order)
                        order["doc_id"] = doc_ref.id
                        st.session_state.orders.append(order)
                        
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Order received!")
                        st.balloons()
                        st.rerun()
                
                with col2:
                    if st.button(":material/phone_iphone: Pay with UPI", width="stretch"):
                        st.info("🔄 Opening UPI payment gateway...")
                        # TODO: Integrate Razorpay UPI
                
                        order['payment_method'] = 'UPI'
                        order['payment_status'] = 'Paid'
                        _, doc_ref = db.collection("orders").add(order)
                        order["doc_id"] = doc_ref.id
                        st.session_state.orders.append(order)
                
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Payment received!")
                        st.balloons()
                        st.rerun()
                     
                with col3:
                    if st.button(":material/credit_card: Pay with card", width="stretch"):
                        order["payment_method"] = "CARD"
                        order["payment_status"] = "Paid"
                        
                        # ONLY NOW ADD TO ORDERS
                        _, doc_ref = db.collection("orders").add(order)
                        order["doc_id"] = doc_ref.id
                        st.session_state.orders.append(order)
                        
                        st.success(f"✅ Order #{order['order_id']} Confirmed!\n\n🎉 Payment received!")
                        st.balloons()
                        st.rerun()
                st.warning("⚠️ Select a payment method to confirm order!")
            
# ── SHOPPING CART ──
st.subheader(":material/shopping_cart: Your cart")

if not st.session_state.cart:
    st.info("Your cart is empty. Click on items in the menu above to add them!")
else:
    total_price = 0
    for i, item in enumerate(st.session_state.cart):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            size_str = f" ({item['size']})" if item['size'] != "-" else ""
            st.write(f"**{item['item']}**{size_str}")
        with c2:
            st.write(f"₹{item['price']}")
        with c3:
            if st.button(":material/close: Remove", key=f"remove_{i}", width="stretch"):
                st.session_state.cart.pop(i)
                st.rerun()
        total_price += item['price']
        
    st.markdown(f"### Total: ₹{total_price}")
    st.divider()
    st.subheader(":material/confirmation_number: Apply coupon code")
    coupon_code = st.text_input("Enter coupon code (optional):", placeholder="e.g., WELCOME10")

    final_total = total_price
    discount = 0
    if coupon_code:
        final_total, discount, message = applied_offer(coupon_code, st.session_state.cart, total_price)
        if discount > 0:
            st.success(f"✅ {message} — Discount: ₹{discount}")
        else:
            st.warning(message)
    st.markdown(f"### 💰 Final Total: ₹{final_total}")

            
    with st.form("checkout_form"):
        customer_name = st.text_input("📝 Your name to complete order:", placeholder="Enter your name")
        submitted = st.form_submit_button(":material/payments: Continue to payment", type="primary", width="stretch")
        
        if submitted and customer_name:
            items_list = [
                {
                    "item": item['item'],
                    "size": item['size'],
                    "price": item['price']
                } for item in st.session_state.cart
            ]
            primary_coffee = ", ".join([it["item"] for it in items_list])
            st.session_state.pending_cart_order = {
                "order_id": next_order_number(),
                "name": customer_name,
                "table": st.session_state.table_number,
                "coffee": primary_coffee,
                "size": "",
                "items": items_list,
                "time": datetime.now().strftime("%H:%M"),
                "created_at": datetime.now().isoformat(),
                "status": "pending",
                "coupon_code": coupon_code.strip().upper() if coupon_code else "",
                "discount": discount,
                "final_total": final_total
            }
            st.rerun()
        elif submitted and not customer_name:
            st.error("Please enter your name before proceeding")

    if st.session_state.get("pending_cart_order"):
        pending_o = st.session_state.pending_cart_order
        st.divider()
        st.subheader(":material/payments: Payment required to confirm order")
        st.warning(f"⚠️ Select payment method to confirm {pending_o['name']}'s order!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button(":material/point_of_sale: Cash on counter", key="cart_cash", width="stretch"):
                pending_o["payment_method"] = "Cash"
                pending_o["payment_status"] = "Pay at counter"
                _, doc_ref = db.collection("orders").add(pending_o)
                pending_o["doc_id"] = doc_ref.id
                st.session_state.orders.append(pending_o)
                st.session_state.cart = []
                st.session_state.pending_cart_order = None
                st.success("✅ Order confirmed & sent to kitchen!")
                st.balloons()
                st.rerun()
        with col2:
            if st.button(":material/phone_iphone: Pay with UPI", key="cart_upi", width="stretch"):
                pending_o["payment_method"] = "UPI"
                pending_o["payment_status"] = "Paid"
                _, doc_ref = db.collection("orders").add(pending_o)
                pending_o["doc_id"] = doc_ref.id
                st.session_state.orders.append(pending_o)
                st.session_state.cart = []
                st.session_state.pending_cart_order = None
                st.success("✅ Order confirmed & sent to kitchen!")
                st.balloons()
                st.rerun()
        with col3:
            if st.button(":material/credit_card: Pay with card", key="cart_card", width="stretch"):
                pending_o["payment_method"] = "CARD"
                pending_o["payment_status"] = "Paid"
                _, doc_ref = db.collection("orders").add(pending_o)
                pending_o["doc_id"] = doc_ref.id
                st.session_state.orders.append(pending_o)
                st.session_state.cart = []
                st.session_state.pending_cart_order = None
                st.success("✅ Order confirmed & sent to kitchen!")
                st.balloons()
                st.rerun()
# ----------- 
# ----- CURRANT ORDER -------
if st.session_state.orders:
    st.divider()
    
    active_orders = [o for o in st.session_state.orders if o.get('status') in ['pending', 'preparing']]
    if active_orders:
        st.info(f"🔥 The kitchen is currently preparing {len(active_orders)} orders.")

    ready_orders = [o for o in st.session_state.orders if o.get('status') == 'ready']
    for ready_o in ready_orders:
        st.success(f"🔔 **Order #{ready_o['order_id']} is READY — please collect your {ready_o.get('coffee', 'order')}!** 🛎️")
        
    tab_current, tab_history = st.tabs([":material/receipt_long: Current orders", ":material/history: Order history"])

    with tab_current:
        # Auto-refresh if there are active orders
        if active_orders:
            try:
                from streamlit_autorefresh import st_autorefresh
                st_autorefresh(interval=5000, key="order_refresh")
            except ImportError:
                pass

        has_current = False
        for order in reversed(st.session_state.orders):
            if order.get('status') == 'completed':
                continue
                
            has_current = True
            # Sync with Firebase if we have doc_id
            if "doc_id" in order:
                doc = db.collection("orders").document(order["doc_id"]).get()
                if doc.exists:
                    db_data = doc.to_dict()
                    order['status'] = db_data.get('status', order.get('status', 'pending'))
                    if 'estimated_time' in db_data:
                        order['estimated_time'] = db_data['estimated_time']
                    if 'preparing_at' in db_data:
                        order['preparing_at'] = db_data['preparing_at']
                    if 'ready_at' in db_data:
                        order['ready_at'] = db_data['ready_at']

                    if order['status'] == 'ready' and (order.get("doc_id") or order.get("order_id")) not in st.session_state.ready_notified:
                        st.session_state.ready_notified.add(order.get("doc_id") or order.get("order_id"))
                        st.balloons()
                        st.toast(f"🔔 Order #{order.get('order_id')} is READY — please take it!", icon="🛎️")

            # Live countdown for preparing orders (same numbers chef app shows)
            countdown_str = ""
            if order.get('status') == 'preparing':
                est_mins = order.get('estimated_time', 5)
                prep_raw = order.get('preparing_at') or order.get('created_at') or datetime.now().isoformat()
                try:
                    prep_time = datetime.fromisoformat(prep_raw)
                except Exception:
                    prep_time = datetime.now()
                elapsed = (datetime.now() - prep_time).total_seconds()
                total_secs = max(1, est_mins * 60)
                remaining = max(0, total_secs - int(elapsed))
                mm, ss = divmod(remaining, 60)
                countdown_str = f"{mm:02d}:{ss:02d}"

            with st.container():
                col1,col2,col3 = st.columns([3,2,1])
                with col1:
                    st.write(f"**#{order['order_id']} - {order['name']}**")
                    if order.get("items"):
                        for sub_item in order["items"]:
                            size_str = f" ({sub_item['size']})" if sub_item.get('size') and sub_item.get('size') != "-" else ""
                            st.write(f"☕ {sub_item.get('item', sub_item.get('item_name'))}{size_str}")
                    else:
                        st.write(f"☕ {order.get('size', '')} {order.get('coffee', '')}")
                    
                    if order.get('status') == 'preparing':
                        st.warning(f"👨‍🍳 **Chef is preparing your order — please wait ~{est_mins} min**\n\n⏳ Ready in {countdown_str}")
                        st.progress(min(1.0, elapsed / total_secs))
                    elif order.get('status') == 'ready':
                        st.success("🔔 **Your order is READY! Please collect it!** 🛎️")
                        
                with col2:
                    if order.get('status') == 'preparing':
                        st.write(f"⏳ **{countdown_str}** left")
                        st.write("📌 Status: **PREPARING**")
                    elif order.get('status') == 'ready':
                        st.write("✅ **Ready — collect it!**")
                        st.write("📌 Status: **READY**")
                    else:
                        st.write(f"🕘 Placed at: {order.get('time', '')}")
                        st.write("📌 Status: **PENDING**")
                with col3:
                    done_key = order.get("doc_id") or order.get("order_id")
                    if st.button(":material/check: Done", key=f"done_{done_key}", width="stretch"):
                        order['status'] = "completed"
                        if "doc_id" in order:
                            db.collection("orders").document(order["doc_id"]).update({"status": "completed"})
                        st.session_state.show_receipt_for = order
                        st.rerun()
                st.space("small")
                
        if not has_current:
            st.info("No active orders right now.")

    with tab_history:
        has_history = False
        for order in reversed(st.session_state.orders):
            if order.get('status') == 'completed':
                has_history = True
                with st.container():
                    col1,col2 = st.columns([3,2])
                    with col1:
                        st.write(f"**#{order['order_id']} - {order['name']}**")
                        if order.get("items"):
                            for sub_item in order["items"]:
                                size_str = f" ({sub_item['size']})" if sub_item.get('size') and sub_item.get('size') != "-" else ""
                                st.write(f"☕ {sub_item.get('item', sub_item.get('item_name'))}{size_str}")
                        else:
                            st.write(f"☕ {order.get('size', '')} {order.get('coffee', '')}")
                    with col2:
                        st.write(f"🕘 Placed at: {order.get('time', '')}")
                        st.success(f"✅ COMPLETED")
                    st.space("small")
                    
        if not has_history:
            st.info("Your past orders will appear here.")
else:
    st.info("No orders yet")
st.divider()

# ── ANALYTICS ──
if len(st.session_state.orders) > 0:
    st.divider()
    with st.expander(":material/analytics: Today's analytics"):
        coffee_counts = {}
        for order in st.session_state.orders:
            coffee = order.get('coffee', 'Order')
            coffee_counts[coffee] = coffee_counts.get(coffee, 0) + 1
        st.write("**Popular items today:**")
        for coffee, count in sorted(coffee_counts.items(), key=lambda x: x[1], reverse=True):
            st.write(f"- {coffee}: {count} order(s)")
        total_revenue = 0
        for order in st.session_state.orders:
            if order.get("items"):
                for it in order["items"]:
                    total_revenue += it.get("price", 0)
            else:
                total_revenue += item_price(order.get("coffee", ""), order.get("size", ""))
        st.metric("Estimated revenue", f"₹{total_revenue}")

# ── FOOTER ──
st.caption("Nova AI Coffee Assistant · Built with ❤️ by Farooq · © 2026")
