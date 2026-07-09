import qrcode
import os 

# Creating Folder for qrcode

if not os.path.exists("qr_codes"):
    os.makedirs("qr_codes")
    
# Creating Qr Codes

for table in range(0,10):
    url = url = f"https://aicoffeeshop-32-build-farooq.streamlit.app/?table={table}"
    
# Create Qr Code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=15,
    border=5
)
qr.add_data(url)
qr.make(fit=True)

img = qr.make_image(fill_color="black",back_color="white")

# Save image
filename = f"qr_codes/qr_table_{table}.png"
img.save(filename)
print(f"✅ Created: {filename}")

print("\n🎉 All 10 QR codes generated!")
print("📂 Check: qr_codes/ folder")