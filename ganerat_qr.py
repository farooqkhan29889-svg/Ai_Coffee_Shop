import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image, ImageDraw, ImageFont
import os 

# YOUR SHOP DETAILS
SHOP_NAME = "☕ Nova Coffee Shop"
OWNER_NAME = "By Farooq Khan"

print("🎬 Creating Beautiful QR Codes...\n")

if not os.path.exists("qr_codes"):
    os.makedirs("qr_codes")

# Premium Colors
BG_COLOR = "#1A1A1A"  # Dark premium gray
QR_BG = (26, 26, 26)  # Dark premium gray for QR background
QR_FG = (255, 255, 255) # White QR code
ACCENT_COLOR = "#D4AF37" # Gold accent for coffee theme
TEXT_COLOR = "#FFFFFF"

for table in range(1, 11):
    url = f"https://aicoffeeshop-32-build-farooq.streamlit.app/?table={table}"
    
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=15,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Styled QR
    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=QR_BG, front_color=QR_FG)
    ).convert('RGB')
    
    # Add logo/text inside the QR code center
    qr_draw = ImageDraw.Draw(qr_img)
    try:
        font_logo = ImageFont.truetype("arialbd.ttf", 22)
    except:
        font_logo = ImageFont.load_default()
        
    logo_text = "NOVA\nCOFFEE"
    bbox_logo = qr_draw.multiline_textbbox((0, 0), logo_text, font=font_logo, align="center")
    logo_w = bbox_logo[2] - bbox_logo[0]
    logo_h = bbox_logo[3] - bbox_logo[1]
    
    # Background for the logo to cover QR lines
    bg_w, bg_h = logo_w + 16, logo_h + 16
    cx = (qr_img.width - bg_w) // 2
    cy = (qr_img.height - bg_h) // 2
    
    # Draw dark rectangle in center
    qr_draw.rectangle([cx, cy, cx + bg_w, cy + bg_h], fill=QR_BG)
    # Draw text
    qr_draw.multiline_text((cx + 8, cy + 4), logo_text, fill=ACCENT_COLOR, font=font_logo, align="center")
    
    # Create beautiful frame
    width = qr_img.width + 120
    height = qr_img.height + 280
    
    # Rounded corners background
    final_img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(final_img)
    
    # Paste QR in center
    qr_x = (width - qr_img.width) // 2
    qr_y = 110
    final_img.paste(qr_img, (qr_x, qr_y))
    
    # Border around QR
    draw.rectangle([qr_x-10, qr_y-10, qr_x+qr_img.width+9, qr_y+qr_img.height+9], outline=ACCENT_COLOR, width=4)
    
    # Fonts
    try:
        font_shop = ImageFont.truetype("arialbd.ttf", 40)
        font_owner = ImageFont.truetype("arial.ttf", 22)
        font_table = ImageFont.truetype("arialbd.ttf", 45)
        font_scan = ImageFont.truetype("arialbd.ttf", 26)
    except:
        font_shop = ImageFont.load_default()
        font_owner = ImageFont.load_default()
        font_table = ImageFont.load_default()
        font_scan = ImageFont.load_default()
    
    # Shop Name
    bbox = draw.textbbox((0, 0), SHOP_NAME, font=font_shop)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, 35), SHOP_NAME, fill=ACCENT_COLOR, font=font_shop)
    
    # Table Number
    text_table = f"Table {table}"
    bbox = draw.textbbox((0, 0), text_table, font=font_table)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, qr_y + qr_img.height + 25), text_table, fill=TEXT_COLOR, font=font_table)
    
    # Scan to Order
    text_scan = "SCAN TO ORDER"
    bbox = draw.textbbox((0, 0), text_scan, font=font_scan)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, qr_y + qr_img.height + 85), text_scan, fill=ACCENT_COLOR, font=font_scan)

    # Owner Name
    bbox = draw.textbbox((0, 0), OWNER_NAME, font=font_owner)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, height - 45), OWNER_NAME, fill="#888888", font=font_owner)
    
    filename = f"qr_codes/qr_table_{table}.png"
    final_img.save(filename)
    print(f"✅ Created: {filename}")

print("\n🎉 All 10 Beautiful QR codes generated!")
print("📂 Check: qr_codes/ folder")