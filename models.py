from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Function to get IST time
def ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

class SuperAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    students = db.relationship('Student', backref='school', lazy=True)
    shopkeepers = db.relationship('Shopkeeper', backref='school', lazy=True)
    bank_details = db.relationship('BankDetail', backref='school', lazy=True, uselist=False)
    payment_requests = db.relationship('PaymentRequest', backref='school', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(50), unique=True)
    class_name = db.Column(db.String(20))
    age = db.Column(db.Integer)
    address = db.Column(db.String(255))
    father_name = db.Column(db.String(120))
    phone = db.Column(db.String(15))
    gender = db.Column(db.String(10))
    upi_pin = db.Column(db.String(255), nullable=False)  # Changed from String(6) to String(255) for hashed PIN
    qr_code_path = db.Column(db.String(255))
    balance = db.Column(db.Float, default=0.0)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    parent = db.relationship('Parent', back_populates='student', uselist=False)    
    transactions = db.relationship('Transaction', backref='student', lazy=True)
    payment_requests = db.relationship('PaymentRequest', backref='student', lazy=True)

    def verify_upi_pin(self, pin):
        """Verify the UPI PIN"""
        return check_password_hash(self.upi_pin, pin)

class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship('Student', back_populates='parent')

class Shopkeeper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)    
    phone = db.Column(db.String(15))
    address = db.Column(db.String(255))
    password = db.Column(db.String(120))
    balance = db.Column(db.Float, default=0.0)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='shopkeeper', lazy=True)
    settlements = db.relationship('ShopkeeperSettlement', backref='shopkeeper', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    shopkeeper_id = db.Column(db.Integer, db.ForeignKey('shopkeeper.id'), nullable=True) 
    amount = db.Column(db.Float)
    description = db.Column(db.String(255))
    friend_name = db.Column(db.String(150))
    mode = db.Column(db.String(20), nullable=False) 
    friend_id = db.Column(db.String(50))
    is_friend = db.Column(db.Boolean, default=False)
    parent_name = db.Column(db.String(120), nullable=True)
    parent_phone = db.Column(db.String(15), nullable=True)
    timestamp = db.Column(db.DateTime, default=ist_now)  # IST time
    decline_reason = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending') # 'pending', 'completed', 'declined'

class ShopkeeperSettlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shopkeeper_id = db.Column(db.Integer, db.ForeignKey('shopkeeper.id'))
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=ist_now)  # IST time

class Warning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    message = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=ist_now)  # IST time

class BankDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'))
    bank_name = db.Column(db.String(150))
    account_holder = db.Column(db.String(150))
    account_number = db.Column(db.String(100))
    ifsc_code = db.Column(db.String(20))

class PaymentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'))
    amount = db.Column(db.Float)
    utr_number = db.Column(db.String(100))
    screenshot_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='Pending')  # Pending, Approved, Declined
    decline_reason = db.Column(db.String(150), nullable=True)
    timestamp = db.Column(db.DateTime, default=ist_now)  # IST time