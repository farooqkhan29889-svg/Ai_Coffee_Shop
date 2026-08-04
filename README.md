# NOVA AI COFFEE SHOP ☕

An AI-powered coffee shop ordering app. Customers scan a table QR code, chat with **Nova** (an AI waiter) to order, pay, and track orders — while a separate Chef Dashboard shows incoming orders in real time.

Built with **Streamlit**, **Firebase (Firestore)**, **LangChain + Groq**, and **Razorpay**.

## Features

- 🤖 AI waiter chat (English / Hindi) — takes orders by asking for name, item, and size
- 🎤 Voice ordering (Groq Whisper)
- 🛒 Click-to-order cart with coupon discounts
- 💳 Payment selection required before an order is confirmed (Cash / UPI / Card)
- 👨‍🍳 Chef Dashboard with preparing/ready status updates synced via Firestore
- 🧾 Bill generation (English + Hindi)
- 🏷️ Offer/coupon system with percent, flat, and per-item discounts

## Project structure

```
app1.py               # Main customer app (Streamlit)
chef_dashboard.py     # Kitchen dashboard (Streamlit)
payment.py            # Prices, bill calculation, OFFERS registry, applied_offer()
ganerat_qr.py         # Generates table QR codes
images/               # Menu images
qr_codes/             # Generated table QR codes
firebase-key.json     # Firebase service-account key (local dev)
.env                  # Secrets (see below)
```

## Setup

```bash
# 1. Create a virtual environment and install dependencies
uv sync            # or: pip install -r requirements.txt

# 2. Configure your .env file
cp .env.example .env   # if present, otherwise create one
```

`.env` needs:

```
FIREBASE_KEY_FILE=firebase-key.json
GROQ_API_KEY=your_groq_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
```

For cloud deployment, put the same credentials in Streamlit Secrets under `st.secrets["firebase"]`.

## Run the app

```bash
# Customer app
streamlit run app1.py

# Chef dashboard
streamlit run chef_dashboard.py

# Regenerate table QR codes
python ganerat_qr.py
```

## Offer / coupon system

All offers live in one registry in `payment.py`:

```python
OFFERS = {
    "WELCOME10": {"type": "percent", "value": 10, "desc": "10% off your order"},
    "NOVA50":    {"type": "flat",    "value": 50, "desc": "₹50 off your order"},
    "LATTE_OFF": {"type": "item",    "item": "Latte", "value": 50, "desc": "₹50 off Latte"},
}
```

- `percent` → percentage off the cart total
- `flat` → fixed ₹ amount off
- `item` → discount only if that item is in the cart

To add a new offer, add **one line** to the registry — no code changes needed.

`applied_offer(code, cart_item, total_price)` returns `(final_total, discount, message)`.

## Tests

```bash
python test_payment.py
```

## Note

- QR codes point to `https://aicoffeeshop-32-build-farooq.streamlit.app/?table=N` — update the URL in `ganerat_qr.py` if you deploy elsewhere.
- The AI menu in the system prompt and the image menu both exist; keep prices in sync.

Built with ❤️ by Farooq
