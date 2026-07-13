# Student Digital Banking System 💳

This is a web-based digital payment system designed for schools where students aren't allowed to carry phones. The system enables:

- Secure login for School Admin, Parents, and Shopkeepers
- Rechargeable wallet system for students
- Barcode-based purchases at school shops
- Admin-managed centralized payment tracking

---

## 💡 Key Features

- **Admin (School)** can:
  - Add Students, Parents, and Shopkeepers
  - Track all users
  - Generate barcodes (manual or future QR codes)
  - Settle balances with shopkeepers

- **Parent**:
  - Logs in using email
  - Views child's current balance
  - Recharges wallet via external UPI and updates system balance manually

- **Shopkeeper**:
  - Accepts payments via barcode lookup
  - Amount is deducted from student's balance
  - Can visit admin to cash out their wallet balance

---

## 🛠️ Tech Stack

- **Frontend**: HTML, CSS (Bootstrap 5)
- **Backend**: Flask (Python)
- **Database**: SQLite (or PostgreSQL for centralized hosting)

---

## 🚀 Setup

# Clone the repository  
# Create virtual environment
python -m venv venv

# Activate environment
# For Linux/MacOS:
source venv/bin/activate
# For Windows:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

> App runs at: http://127.0.0.1:5000/


