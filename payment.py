import os
import razorpay
from dotenv import load_dotenv

# Coffee Price

PRICES = {
    "Cappuccino": {"Small": 150, "Medium": 200, "Large": 250},
    "Latte": {"Small": 150, "Medium": 200, "Large": 250},
    "Americano": {"Small": 150, "Medium": 200, "Large": 250},
    "Espresso": {"Small": 150, "Medium": 200, "Large": 250},
    "Mocha": {"Small": 150, "Medium": 200, "Large": 250},
    "Flat White": {"Small": 150, "Medium": 200, "Large": 250},
} 
def create_razorpay_order(amount, customer_name, customer_email):
    """Create Razorpay order for payment"""
    try:
        RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
        RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
        
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        order_data = {
            "amount": amount * 100,  # Convert to paise
            "currency": "INR",
            "receipt": f"order_{customer_name}_{amount}",
        }
        
        order = client.order.create(data=order_data)
        return order["id"]
    except Exception as e:
        print(f"Error: {e}")
        return None

FOOD_PRICES = {
    "Croissant": 120,
    "Chocolate Cake": 150,
    "Muffins": 140,
    "Brownie": 160,
    "Gulab Jamun": 20,
    "Ras Mlai": 15,
}

def calculate_bill(orders):
    """Total calculate_bill price"""
    import re
    bill_items = []
    total = 0
    
    for order in orders:
        if "items" in order and isinstance(order["items"], list):
            for sub_item in order["items"]:
                item_name = sub_item.get("item", sub_item.get("item_name", sub_item.get("coffee", "")))
                size = sub_item.get("size", "")
                price = sub_item.get("price", 0)
                bill_items.append({
                    "item": f"{item_name} ({size})" if size and size != "-" else item_name,
                    "price": price
                })
                total += price
        else:
            coffee = order.get("coffee", "")
            size = order.get("size", "")
            
            if coffee in PRICES and size in PRICES[coffee]:
                price = PRICES[coffee][size]  #  FIXED: Added PRICES
                bill_items.append({
                    "item": f"{coffee} ({size})",
                    "price": price
                })
                total += price
            else:
                # Check if it is a food item
                food_price = None
                for f_name, f_price in FOOD_PRICES.items():
                    if f_name.lower() in coffee.lower():
                        food_price = f_price
                        # Extract quantity from size (e.g. "2 pieces" -> 2)
                        qty = 1
                        nums = re.findall(r'\d+', size)
                        if nums:
                            qty = int(nums[0])
                        
                        price = food_price * qty
                        bill_items.append({
                            "item": f"{coffee} ({size})",
                            "price": price
                        })
                        total += price
                        break
                
                # Fallback if unknown
                if food_price is None:
                    bill_items.append({
                        "item": f"{coffee} ({size})",
                        "price": 100
                    })
                    total += 100
    
    return {
        "items": bill_items,  #  FIXED: Changed "item" to "items"
        "total": total
    } 
    
    
def generate_bill_text(bill_data, language="English"):
    """Generate formatted bill text"""
    if language == "Hindi IN":
        bill_text = " आपका बिल\n"
        bill_text += "="*30 + "\n"
        for item in bill_data["items"]:
            bill_text += f"☕ {item['item']}: ₹{item['price']}\n"
        bill_text += "="*30 + "\n"
        bill_text += f"कुल: ₹{bill_data['total']}\n"
    else:
        bill_text = " Your Bill\n"
        bill_text += "="*30 + "\n"
        for item in bill_data["items"]:
            bill_text += f"☕ {item['item']}: ₹{item['price']}\n"
        bill_text += "="*30 + "\n"
        bill_text += f"Total: ₹{bill_data['total']}\n"
    
    return bill_text

OFFERS = {
    "WELCOME10": {"type": "percent", "value": 10, "desc": "10% off your order"},
    "SAVE20":    {"type": "percent", "value": 20, "desc": "20% off your order"},
    "FIRST30":   {"type": "percent", "value": 30, "desc": "30% off your order"},
    "NOVA50":    {"type": "flat",    "value": 50, "desc": "₹50 off your order"},
    "NOVA100":   {"type": "flat",    "value": 100, "desc": "₹100 off your order"},
    "LATTE_OFF": {"type": "item",    "item": "Latte", "value": 50, "desc": "₹50 off Latte"},
}

def applied_offer(code, cart_item, total_price):
    """Return (final_total, discount_amount, message).

    cart_item is a list of {'item': ..., 'size': ..., 'price': ...}
    total_price is the pre-discount cart total.
    """
    code = code.strip().upper()
    if code not in OFFERS:
        return (total_price, 0, "Invalid code")

    offer = OFFERS[code]
    discount = 0

    if offer["type"] == "flat":
        discount = offer["value"]
    elif offer["type"] == "percent":
        discount = int(total_price * offer["value"] / 100)
    elif offer["type"] == "item":
        for item in cart_item:
            if item["item"] == offer["item"]:
                discount = offer["value"]
                break
        if discount == 0:
            return (total_price, 0, f"{code} needs {offer['item']} in your cart")

    return (max(0, total_price - discount), discount, offer["desc"])

    
def apply_coupon(coupon_code, total_amount):
    """Apply discount coupon code"""
    code = coupon_code.strip().upper() if coupon_code else ""
    if code == "NOVA50":
        return max(0, total_amount - 50), 50
    elif code == "NOVA100":
        return max(0, total_amount - 100), 100
    else:
        return total_amount, 0
    