import os
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

def calculate_bill(orders):
    """Total calculate_bill price"""
    bill_items = []
    total = 0
    
    for order in orders:
        coffee = order.get("coffee")
        size = order.get("size")
        
        if coffee in PRICES and size in PRICES[coffee]:
            price = PRICES[coffee][size]  #  FIXED: Added PRICES
            bill_items.append({
                "item": f"{coffee} ({size})",
                "price": price
            })
            
            total += price
    
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