from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, Student, Parent, Shopkeeper, Transaction, School, BankDetail, PaymentRequest, ShopkeeperSettlement
from datetime import datetime
from reportlab.pdfgen import canvas
from sqlalchemy import or_
import re,os,qrcode,uuid
import json


from dotenv import load_dotenv
load_dotenv()

# --- CORRECT ORDER ---
# 1. Create the app
app = Flask(__name__)

# 2. Load the config into the app
app.config.from_object(Config) 

# 3. Now you can use 'app' for decorators
@app.after_request
def add_header(response):
    """
    Add headers to prevent caching on all dynamic pages.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

app.config['UPLOAD_FOLDER'] = 'static/qrcodes'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
mail = Mail(app)

WHITELISTED_DOMAINS = ['edu.in', 'school.org', 'ac.in']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register_school', methods=['GET', 'POST'])
def register_school():
    if request.method == 'POST':
        school_name = request.form['school_name']
        phone = request.form['phone']
        email = request.form['email']
        pincode= request.form['pincode']
        location=request.form['location']
        password = request.form['password']
        repassword = request.form['confirmPassword']
        domain = email.split('@')[1]

        if not any(email.endswith(domain) for domain in WHITELISTED_DOMAINS):
            flash('Only educational domain emails (.edu.in or .ac.in) are allowed.', 'danger')
            return render_template('index.html')
        # Email uniqueness check
        existing_school = School.query.filter_by(email=email).first()
        if existing_school:
            flash('A school with this email already exists.', 'warning')
            return render_template('index.html')
        # Password match check
        if password != repassword:
            flash('Passwords do not match.', 'danger')
            return render_template('index.html')
        # Add school to DB
        new_school = School(
            name=school_name,
            phone=phone,
            email=email,
            location=location,
            pincode=pincode,
            password=generate_password_hash(password)
        )
        db.session.add(new_school)
        db.session.commit()
        flash('School registered successfully. Please login.', 'success')
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        
        # Super Admin login
        if email == app.config['SUPER_ADMIN_EMAIL'] and pw == app.config['SUPER_ADMIN_PASSWORD']:
            session['role'] = 'superadmin'
            session['user'] = email
            flash("Logged in as Super Admin", "success")
            return redirect(url_for('superadmin_dashboard'))
        
        # School Admin login
        admin = School.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, pw):
            session['role'] = 'admin'
            session['user'] = email
            session['school_id'] = admin.id
            flash("Logged in as School Admin", "success")
            return redirect(url_for('admin_dashboard'))

        # Parent login
        parent = Parent.query.filter_by(email=email).first()
        if parent and check_password_hash(parent.password, pw):
            session['role'] = 'parent'
            session['user'] = email
            session['parent_id'] = parent.id 
            flash("Logged in as Parent", "success")
            return redirect(url_for('parent_dashboard'))

        # Shopkeeper login
        user = Shopkeeper.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, pw):
            session['role'] = 'shopkeeper'
            session['user'] = email
            session['shopkeeper_id'] = user.id
            flash("Logged in as Shopkeeper", "success")
            return redirect(url_for('shopkeeper_dashboard'))

        flash("Invalid credentials", "danger")
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/superadmin/dashboard')
def superadmin_dashboard():
    if session.get('role') != 'superadmin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    schools = School.query.all()
    return render_template('superadmin_dashboard.html', schools=schools)

@app.route('/superadmin/delete_school/<int:id>', methods=['POST'])
def delete_school(id):
    if session.get('role') != 'superadmin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    school = School.query.get(id)
    if school:
        email = school.email
        db.session.delete(school)
        db.session.commit()
        msg = Message("Account Removed", sender=Config.MAIL_USERNAME, recipients=[email])
        msg.body = f"Dear Admin,\nYour account {email} has been removed."
        try:
            mail.send(msg)
            flash("School deleted and email sent", "success")
        except Exception as e:
            flash(f"School deleted but email failed: {e}", "warning")
    else:
        flash("School not found", "danger")
    return redirect(url_for('superadmin_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    school_id = session.get('school_id')
    if not school_id:
        flash('Session error. Please log in again.', 'danger')
        session.clear()
        return redirect(url_for('login'))
    
    school = School.query.get(school_id)
    
    if not school:
        flash('Your associated school account could not be found. You have been logged out.', 'danger')
        session.clear()
        return redirect(url_for('login'))
    
    # Get search parameters
    field = request.args.get('field', '').strip()
    query = request.args.get('query', '').strip()
    
    # Define searchable fields
    student_fields = {'name', 'student_id', 'class_name', 'father_name', 'phone'}
    shopkeeper_fields = {'name', 'email', 'phone', 'address'}
    
    # Initialize variables
    show_students = True
    show_shopkeepers = True
    students = []
    parents = []
    shopkeepers = []
    
    # Fetch data based on search
    if field and query:
        if field in student_fields:
            show_students = True
            show_shopkeepers = False
            students = Student.query.filter(
                getattr(Student, field).ilike(f"%{query}%"),
                Student.school_id == school_id
            ).all()
            student_ids = [s.id for s in students]
            parents = Parent.query.filter(Parent.student_id.in_(student_ids)).all()
            shopkeepers = []
        elif field in shopkeeper_fields:
            show_students = False
            show_shopkeepers = True
            shopkeepers = Shopkeeper.query.filter(
                getattr(Shopkeeper, field).ilike(f"%{query}%"),
                Shopkeeper.school_id == school_id
            ).all()
            students = []
            parents = []
        else:
            # Invalid field, show all
            students = Student.query.filter_by(school_id=school_id).all()
            student_ids = [s.id for s in students]
            parents = Parent.query.filter(Parent.student_id.in_(student_ids)).all()
            shopkeepers = Shopkeeper.query.filter_by(school_id=school_id).all()
    else:
        # No search, show all
        students = Student.query.filter_by(school_id=school_id).all()
        student_ids = [s.id for s in students]
        parents = Parent.query.filter(Parent.student_id.in_(student_ids)).all()
        shopkeepers = Shopkeeper.query.filter_by(school_id=school_id).all()
    
    # Pending payment requests
    student_ids = [s.id for s in students]
    pending_transactions = PaymentRequest.query.filter(
        PaymentRequest.status == 'Pending',
        PaymentRequest.student_id.in_(student_ids)
    ).all() if student_ids else []
    
    # Bank details
    bank_detail = BankDetail.query.filter_by(school_id=school_id).first()
    bank_message = None if bank_detail else "No bank account added."
    
    return render_template('dashboard_admin.html',
                         school=school,
                         students=students,
                         parents=parents,
                         shopkeepers=shopkeepers,
                         pending_transactions=pending_transactions,
                         bank_detail=bank_detail,
                         bank_message=bank_message,
                         field=field,
                         query=query,
                         show_students=show_students,
                         show_shopkeepers=show_shopkeepers)

@app.route('/admin/add_bank', methods=['POST'])
def add_bank():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    school_id = session.get('school_id')
    
    # Get form data from modal
    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    re_account_number = request.form.get('re_account_number')
    ifsc_code = request.form.get('ifsc_code')

    # Enhanced validation
    if not all([bank_name, account_number, re_account_number, ifsc_code]):
        flash("All fields are required!", "danger")
        return redirect(url_for('admin_dashboard'))

    # Check if account numbers match
    if account_number != re_account_number:
        flash("Account numbers do not match!", "danger")
        return redirect(url_for('admin_dashboard'))

    # Check if bank account already exists FOR THIS SCHOOL
    existing_bank = BankDetail.query.filter_by(school_id=school_id).first()
    if existing_bank:
        flash("Bank account already exists! Please delete the existing account before adding a new one.", "danger")
        return redirect(url_for('admin_dashboard'))

    # Add new bank (only if no existing bank for this school)
    new_bank = BankDetail(
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        school_id=school_id  # ADD THIS LINE
    )
    db.session.add(new_bank)
    db.session.commit()
    flash("Bank account added successfully.", "success")

    return redirect(url_for('admin_dashboard'))

# --- UPDATED ROUTE ---
@app.route('/admin/add_student', methods=['POST'])
def add_student():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    school_id = session.get('school_id')
    name = request.form['name']
    student_id_input = request.form['student_id']
    student_class = request.form['student_class']
    age = request.form['age']
    address = request.form['address']
    father_name = request.form['father_name']
    phone = request.form['phone']
    gender = request.form['gender'] # New field
    password = request.form['parent_password']
    upi_pin = request.form['upi_pin']
    
    # New parent fields
    parent_phone = request.form['parent_phone']
    parent_address = request.form['parent_address']


    # Check if Student ID already exists
    existing_student = Student.query.filter_by(student_id=student_id_input, school_id=school_id).first()
    if existing_student:
        flash("Student ID already exists. Please use a different ID.", "danger")
        return redirect(url_for('admin_dashboard'))

    # Generate QR code for student
    qr_data = f"{student_id_input}"
    qr_img = qrcode.make(qr_data)
    qr_filename = f"{student_id_input}.png"
    qr_folder = os.path.join('static', 'qrcodes')
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, qr_filename)
    qr_img.save(qr_path)

    hashed_upi_pin = generate_password_hash(upi_pin)
    # Create Student
    student = Student(
        name=name,
        student_id=student_id_input,
        class_name=student_class,
        age=age,
        address=address,
        father_name=father_name,
        phone=phone,
        gender=gender, # New field
        upi_pin=hashed_upi_pin,
        qr_code_path=qr_filename,
        school_id=school_id,
        balance=0.0
    )
    db.session.add(student)
    db.session.commit()

    # Create Parent linked to the student
    school = School.query.get(school_id)
    school_name_cleaned = school.name.lower().replace(' ', '')
    parent_email = f"{student_id_input}p{school_name_cleaned}@gmail.com"

    parent = Parent(
        email=parent_email,
        password=generate_password_hash(password),
        phone=parent_phone,     # New field
        address=parent_address, # New field
        student_id=student.id
    )
    db.session.add(parent)
    db.session.commit()

    flash("Student and linked Parent account created successfully.", "success")
    return redirect(url_for('admin_dashboard'))

# --- UPDATED ROUTE ---
@app.route('/admin/edit_student/<int:student_id>', methods=['POST'])
def edit_student(student_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    student = Student.query.get_or_404(student_id)
    
    if student.school_id != session.get('school_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # Get form data from modal
    student.name = request.form['name']
    student_id_new = request.form['student_id']
    student.class_name = request.form['student_class']
    student.age = request.form['age']
    student.address = request.form['address']
    student.father_name = request.form['father_name']
    student.phone = request.form['phone']
    student.gender = request.form['gender'] # New field
    
    new_upi_pin = request.form['upi_pin']
    if new_upi_pin: 
        student.upi_pin = generate_password_hash(new_upi_pin)    
    
    # Update QR code if student ID changed
    if student_id_new != student.student_id:
        # Delete old QR code
        if student.qr_code_path:
            old_path = os.path.join("static/qrcodes", student.qr_code_path)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Generate new QR code
        qr_data = f"{student_id_new}"
        qr_img = qrcode.make(qr_data)
        qr_code_path = f"{student_id_new}.png"
        qr_path = os.path.join("static/qrcodes", qr_code_path)
        qr_img.save(qr_path)
        student.qr_code_path = qr_code_path
        student.student_id = student_id_new

    db.session.commit()
    flash("Student updated successfully", "success")
    return redirect(url_for('admin_dashboard'))

# --- NEW ROUTE for Admin to add/remove money ---
@app.route('/admin/adjust_balance/<int:student_id>', methods=['POST'])
def adjust_balance(student_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    student = Student.query.get_or_404(student_id)
    
    # Security check
    if student.school_id != session.get('school_id'):
        flash("Unauthorized access. This student does not belong to your school.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        amount = float(request.form['amount'])
        reason = request.form['reason']
        transaction_type = request.form['transaction_type'] # 'add' or 'remove'
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for('admin_dashboard'))
    except KeyError:
        flash("Missing form data.", "danger")
        return redirect(url_for('admin_dashboard'))

    if amount <= 0:
        flash("Amount must be a positive number.", "danger")
        return redirect(url_for('admin_dashboard'))

    if not reason:
        flash("A reason is required for this transaction.", "danger")
        return redirect(url_for('admin_dashboard'))

    transaction_amount = 0.0
    description_prefix = ""

    if transaction_type == 'add':
        student.balance += amount
        transaction_amount = amount
        description_prefix = "Admin Credit"
        flash(f"₹{amount} successfully added to {student.name}'s balance.", "success")

    elif transaction_type == 'remove':
        if student.balance < amount:
            flash(f"Cannot remove ₹{amount}. Student's balance is only ₹{student.balance}.", "danger")
            return redirect(url_for('admin_dashboard'))
        student.balance -= amount
        transaction_amount = -amount # Negative for removal
        description_prefix = "Admin Debit"
        flash(f"₹{amount} successfully removed from {student.name}'s balance.", "success")
        
    else:
        flash("Invalid transaction type.", "danger")
        return redirect(url_for('admin_dashboard'))

    # Log the transaction
    admin_transaction = Transaction(
        student_id=student.id,
        shopkeeper_id=None, # Admin transaction
        amount=transaction_amount,
        description=f"{description_prefix}: {reason}",
        mode="admin_adjustment",
        status="completed",
        timestamp=datetime.now()
    )
    db.session.add(admin_transaction)
    db.session.commit()

    return redirect(url_for('admin_dashboard'))


# In /admin/delete_student/<int:student_id>
@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    student = Student.query.get_or_404(student_id)
    if student.school_id != session.get('school_id'):
        flash("Unauthorized access. This student does not belong to your school.", "danger")
        return redirect(url_for('admin_dashboard'))
    # Delete QR code file
    if student.qr_code_path:  
        qr_path = os.path.join('static', 'qrcodes', student.qr_code_path)
        if os.path.exists(qr_path):
            os.remove(qr_path)
    # Delete associated parent
    parent = Parent.query.filter_by(student_id=student_id).first()
    if parent:
        db.session.delete(parent)
    db.session.delete(student)
    db.session.commit()
    flash(f"Student '{student.name}' and all related data deleted successfully.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_shopkeeper', methods=['POST'])
def add_shopkeeper():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    name = request.form['name']
    phone = request.form['phone']
    address = request.form['address']
    password = request.form['password']
    school_id = session.get('school_id')

    school = School.query.get(school_id)

    # Auto-generate email
    cleaned_name = name.strip().lower().replace(" ", "")
    cleaned_school = school.name.strip().lower().replace(" ", "")
    generated_email = f"{cleaned_name}{cleaned_school}@gmail.com"

    # Check if email already exists
    if Shopkeeper.query.filter_by(email=generated_email).first():
        flash("Shopkeeper with this generated email already exists.", "danger")
        return redirect(url_for('admin_dashboard'))

    new_shopkeeper = Shopkeeper(
        name=name,
        phone=phone,
        email=generated_email,
        password=generate_password_hash(password),
        address=address,
        school_id=school_id,
        balance=0.0
    )
    db.session.add(new_shopkeeper)
    db.session.commit()
    flash("Shopkeeper added successfully", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_shopkeeper/<int:shopkeeper_id>', methods=['POST'])
def edit_shopkeeper(shopkeeper_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    shopkeeper = Shopkeeper.query.get_or_404(shopkeeper_id)
    
    if shopkeeper.school_id != session.get('school_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # Get form data from modal
    shopkeeper.name = request.form['name']
    shopkeeper.email = request.form['email']
    shopkeeper.phone = request.form['phone']
    shopkeeper.address = request.form['address']
    new_password = request.form.get('password')
    
    # Only update password if a new one was provided
    if new_password and new_password.strip():
        shopkeeper.password = generate_password_hash(new_password)
    
    db.session.commit()
    flash("Shopkeeper details updated successfully", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_shopkeeper/<int:shopkeeper_id>', methods=['POST'])
def delete_shopkeeper(shopkeeper_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    shopkeeper = Shopkeeper.query.get_or_404(shopkeeper_id) # Changed to 404
    
    if shopkeeper.school_id != session.get('school_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('admin_dashboard'))
    
    db.session.delete(shopkeeper)
    db.session.commit()
    flash("Shopkeeper deleted successfully", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/bank_details', methods=['GET', 'POST'])
def admin_bank_details():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    school_id = session.get('school_id')
    details = BankDetail.query.filter_by(school_id=school_id).first()

    if request.method == 'POST':
        account_holder = request.form['account_holder']
        account_number = request.form['account_number']
        ifsc_code = request.form['ifsc_code']
        bank_name = request.form['bank_name']

        if details:
            details.account_holder = account_holder
            details.account_number = account_number
            details.ifsc_code = ifsc_code
            details.bank_name = bank_name
        else:
            details = BankDetail(
                school_id=school_id,
                account_holder=account_holder,
                account_number=account_number,
                ifsc_code=ifsc_code,
                bank_name=bank_name
            )
            db.session.add(details)
        
        db.session.commit()
        flash("Bank details updated successfully!", "success")
        return redirect(url_for('admin_bank_details'))

    return render_template("admin_bank_details.html", details=details)

@app.route('/admin/delete_bank', methods=['GET']) 
def delete_bank():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    school_id = session.get('school_id')
    bank = BankDetail.query.filter_by(school_id=school_id).first()
    
    if bank:
        db.session.delete(bank)
        db.session.commit()
        flash("Bank account deleted successfully.", "info")
    else:
        flash("No bank account found to delete.", "warning")

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify_transactions')
def admin_verify_transactions():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    school_id = session.get('school_id')
    pending_requests = PaymentRequest.query.filter_by(
        school_id=school_id, 
        status='Pending'
    ).order_by(PaymentRequest.timestamp.desc()).all()

    return render_template('verify_transactions.html', payment_requests=pending_requests)

@app.route('/admin/approve_payment/<int:request_id>', methods=['POST'])
def admin_approve_payment(request_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    payment_request = PaymentRequest.query.get_or_404(request_id)
    student = Student.query.get(payment_request.student_id)

    if not student or student.school_id != session.get('school_id'):
        flash('Unauthorized or invalid payment request.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if payment_request.status != 'Pending':
        flash('Payment request already processed.', 'warning')
        return redirect(url_for('admin_dashboard'))

    student.balance += payment_request.amount
    payment_request.status = 'Approved'
    db.session.commit()

    flash(f'Payment approved and ₹{payment_request.amount} added to {student.name} balance.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/decline_payment/<int:payment_id>', methods=['POST'])
def admin_decline_payment(payment_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    reason = request.form.get('decline_reason')
    if not reason or reason.strip() == "":
        flash("Decline reason is required.", "danger")
        return redirect(url_for('admin_dashboard'))

    payment = PaymentRequest.query.get(payment_id)
    if not payment:
        flash("Payment request not found.", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # Security Check
    if payment.student.school_id != session.get('school_id'):
        flash("Unauthorized access to this payment request.", "danger")
        return redirect(url_for('admin_dashboard'))

    payment.status = "Declined"
    payment.decline_reason = reason.strip()
    db.session.commit()

    flash("Payment request declined successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_parent_password/<int:parent_id>', methods=['GET', 'POST'])
def reset_parent_password(parent_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    parent = Parent.query.get_or_404(parent_id)
    
    # Security Check
    if parent.student.school_id != session.get('school_id'):
        flash("Unauthorized access to this parent.", "danger")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('reset_parent_password', parent_id=parent.id))

        parent.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Parent password reset successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('reset_parent_password.html', parent=parent)

@app.route('/admin/reset_shopkeeper_password/<int:shopkeeper_id>', methods=['POST'])
def reset_shopkeeper_password(shopkeeper_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    shopkeeper = Shopkeeper.query.get_or_404(shopkeeper_id)
    
    if shopkeeper.school_id != session.get('school_id'):
        flash("Unauthorized access", "danger")
        return redirect(url_for('admin_dashboard'))
    
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('admin_dashboard'))

    shopkeeper.password = generate_password_hash(new_password)
    db.session.commit()
    flash('Password reset successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settle_balance/<int:shopkeeper_id>', methods=['POST'])
def settle_balance(shopkeeper_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    shopkeeper = Shopkeeper.query.get_or_404(shopkeeper_id)
    
    if shopkeeper.school_id != session.get('school_id'):
        flash('Unauthorized access to this shopkeeper', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        amount = float(request.form.get('settle_amount', 0))
    except (ValueError, TypeError):
        flash('Invalid amount provided', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if amount <= 0:
        flash('Settle amount must be greater than 0', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    current_balance = shopkeeper.balance if shopkeeper.balance else 0.0
    
    if amount > current_balance:
        flash(f'Settle amount (₹{amount}) cannot exceed current balance (₹{current_balance})', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Update shopkeeper's balance
    shopkeeper.balance = current_balance - amount
    
    # Create settlement record
    settlement = ShopkeeperSettlement(
        shopkeeper_id=shopkeeper.id,
        amount=amount,
        timestamp=datetime.now()
    )
    
    # Create transaction record
    transaction = Transaction(
        shopkeeper_id=shopkeeper.id,
        student_id=None,
        amount=-amount,
        description=f"Admin settlement - ₹{amount}",
        mode="admin_settlement",
        timestamp=datetime.now(),
        status="completed"    
    )
    
    db.session.add(settlement)
    db.session.add(transaction)
    db.session.commit()
    
    flash(f'Successfully settled ₹{amount} with {shopkeeper.name}. Remaining balance: ₹{shopkeeper.balance}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settlement_history/<int:shopkeeper_id>')
def settlement_history(shopkeeper_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized access'}), 401
    
    try:
        shopkeeper = Shopkeeper.query.get_or_404(shopkeeper_id)
        
        if shopkeeper.school_id != session.get('school_id'):
            return jsonify({'error': 'Unauthorized access to this shopkeeper'}), 403
        
        settlements = ShopkeeperSettlement.query.filter_by(
            shopkeeper_id=shopkeeper_id
        ).order_by(ShopkeeperSettlement.timestamp.desc()).all()
        
        total_settled = sum(settlement.amount for settlement in settlements)
        last_settlement_date = settlements[0].timestamp.strftime('%Y-%m-%d %H:%M') if settlements else None
        
        settlements_data = []
        for settlement in settlements:
            settlements_data.append({
                'id': settlement.id,
                'amount': settlement.amount,
                'timestamp': settlement.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'formatted_amount': f"₹{settlement.amount:.2f}",
                'formatted_date': settlement.timestamp.strftime('%b %d, %Y %I:%M %p')
            })
        
        return jsonify({
            'shopkeeper': {
                'name': shopkeeper.name,
                'balance': shopkeeper.balance if shopkeeper.balance else 0.0
            },
            'settlements': settlements_data,
            'summary': {
                'total_settlements': len(settlements),
                'total_settled': total_settled,
                'last_settlement_date': last_settlement_date
            }
        })
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# --- NEW API ROUTE for student history ---
@app.route('/api/admin/student_history/<int:student_id>')
def admin_student_history(student_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized access'}), 401

    student = Student.query.get_or_404(student_id)
    
    # Security Check
    if student.school_id != session.get('school_id'):
        return jsonify({'error': 'Unauthorized access to this student'}), 403

    # Get all transactions (spending, admin adjustments)
    transactions = Transaction.query.filter_by(student_id=student.id).all()
    
    # Get all payment requests (parent deposits)
    payment_requests = PaymentRequest.query.filter_by(student_id=student.id).all()
    
    history = []

    # Process transactions
    for txn in transactions:
        history.append({
            'type': 'Transaction',
            'date': txn.timestamp.strftime('%Y-%m-%d %H:%M'),
            'description': txn.description,
            'amount': f"₹{txn.amount:.2f}",
            'status': txn.status.title(),
            'amount_class': 'text-danger' if txn.amount < 0 else 'text-success'
        })

    # Process payment requests
    for req in payment_requests:
        history.append({
            'type': 'Payment Request',
            'date': req.timestamp.strftime('%Y-%m-%d %H:%M'),
            'description': f"Parent Deposit (UTR: {req.utr_number})",
            'amount': f"₹{req.amount:.2f}",
            'status': req.status.title(),
            'amount_class': 'text-success' if req.status == 'Approved' else 'text-muted'
        })

    # Sort combined history by date, descending
    history.sort(key=lambda x: x['date'], reverse=True)

    return jsonify({
        'student_name': student.name,
        'student_id': student.student_id,
        'current_balance': f"₹{student.balance:.2f}",
        'history': history
    })


# PARENT ROUTES
@app.route('/parent/dashboard')
def parent_dashboard():
    if session.get('role') != 'parent' or 'user' not in session:
        flash("Please log in as a parent first.", "danger")
        return redirect(url_for('login'))

    parent = Parent.query.filter_by(email=session['user']).first()
    if not parent:
        flash("Parent account not found", "danger")
        return redirect(url_for('login'))

    student = parent.student
    if not student:
        flash("No linked student found", "danger")
        return redirect(url_for('login'))

    transactions = Transaction.query.filter_by(
        student_id=student.id
    ).order_by(Transaction.timestamp.desc()).all()

    payment_requests = PaymentRequest.query.filter_by(
        student_id=student.id
    ).order_by(PaymentRequest.timestamp.desc()).all()

    school = School.query.get(student.school_id)

    return render_template(
        'dashboard_parent.html',
        parent=parent,
        student=student,
        transactions=transactions,
        payment_requests=payment_requests,
        school=school
    )

@app.route('/parent/add_money', methods=['POST'])
def parent_add_money():
    if session.get('role') != 'parent' or 'user' not in session:
        flash("Please log in as a parent first.", "danger")
        return redirect(url_for('login'))

    amount = request.form.get('amount')
    utr_number = request.form.get('utr_number')
    screenshot = request.files.get('screenshot')

    if not amount or not utr_number or not screenshot:
        flash("Please fill in all required fields and upload the proof.", "danger")
        return redirect(url_for('parent_dashboard'))

    parent = Parent.query.filter_by(email=session['user']).first()
    if not parent or not parent.student:
        flash("Parent or linked student not found", "danger")
        return redirect(url_for('parent_dashboard'))

    student = parent.student

    # Check duplicate UTR number
    existing_utr = PaymentRequest.query.filter_by(utr_number=utr_number).first()
    if existing_utr:
        flash("This UTR number has already been used. Please check and try again.", "danger")
        return redirect(url_for('parent_dashboard'))

    # Prepare upload folder
    upload_dir = os.path.join('static', 'uploads', 'payment_proofs')
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    filename = secure_filename(screenshot.filename)
    file_ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    save_path = os.path.join(upload_dir, unique_filename)

    # Save file
    screenshot.save(save_path)

    # Create PaymentRequest
    payment_request = PaymentRequest(
        student_id=student.id,
        school_id=student.school_id,
        amount=float(amount),
        utr_number=utr_number,
        screenshot_path=os.path.join('uploads', 'payment_proofs', unique_filename),
        status='Pending'
    )
    db.session.add(payment_request)
    db.session.commit()

    flash("Payment request submitted successfully. Waiting for admin approval.", "success")
    return redirect(url_for('parent_dashboard'))

@app.route('/parent/show_transactions')
def parent_transactions():
    if session.get('role') != 'parent':
        flash("Unauthorized", "danger")
        return redirect(url_for('login'))

    user_email = session.get('user')
    parent = Parent.query.filter_by(email=user_email).first()
    if not parent:
        flash("Parent account not found", "danger")
        return redirect(url_for('login'))

    student = parent.student
    if not student:
        flash("Student linked to parent not found.", "danger")
        return redirect(url_for('login'))

    transactions = Transaction.query.filter_by(
        student_id=student.id
    ).order_by(Transaction.timestamp.desc()).all()

    return render_template('parent_transactions.html', 
                         parent=parent, 
                         student=student, 
                         transactions=transactions)

@app.route('/parent/edit_password', methods=['POST'])
def parent_edit_password():
    if session.get('role') != 'parent':
        flash("Unauthorized", "danger")
        return redirect(url_for('login'))
    
    parent_id = session.get('parent_id')
    parent = Parent.query.get(parent_id)
    
    if not parent:
        flash("Parent not found", "danger")
        return redirect(url_for('login'))
    
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash('Passwords do not match!', 'danger')
        return redirect(url_for('parent_dashboard'))

    parent.password = generate_password_hash(new_password)
    db.session.commit()
    flash('Password updated successfully!', 'success')

    # This route was changed to return JSON for an AJAX request,
    # but the form in dashboard_parent.html is a standard POST.
    # Reverting to redirect.
    return redirect(url_for('parent_dashboard'))


@app.route('/shopkeeper/clear_pending', methods=['POST'])
def clear_pending():
    """Clear pending transaction data"""
    session.pop('pending_student_id', None)
    session.pop('upi_verified', None)
    return '', 200


@app.route('/api/student/<student_id>', methods=['GET'])
def get_student_data(student_id):
    """API endpoint to get student data for modal"""
    student = Student.query.filter_by(student_id=student_id).first()
    
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(student_id=student.id)\
        .order_by(Transaction.timestamp.desc())\
        .limit(5)\
        .all()
    
    transactions_data = []
    for txn in recent_transactions:
        transactions_data.append({
            'description': txn.description,
            'amount': float(txn.amount),
            'timestamp': txn.timestamp.strftime("%Y-%m-%d %H:%M") if txn.timestamp else 'N/A'
        })
    
    return jsonify({
        'id': student.id,
        'name': student.name,
        'student_id': student.student_id,
        'class_name': student.class_name,
        'balance': float(student.balance),
        'recent_transactions': transactions_data
    })

@app.route('/api/verify_upi', methods=['POST'])
def verify_upi():
    data = request.get_json()
    student_id = data.get('student_id')
    upi_pin = data.get('upi_pin')

    student = Student.query.filter_by(student_id=student_id).first()

    if not student:
        return jsonify({'success': False, 'error': 'Student not found'}), 404

    # Use check_password_hash here!
    if check_password_hash(student.upi_pin, upi_pin):
        # We also need to set a session variable here for the next step
        session['upi_verified_student_id'] = student.id
        session['upi_verified_timestamp'] = datetime.now().timestamp()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid UPI PIN'}), 401

# In /api/process_transaction
@app.route('/api/process_transaction', methods=['POST'])
def process_transaction():
    """API endpoint to process the transaction"""
    data = request.get_json()
    student_id_str = data.get('student_id') 
    amount = float(data.get('amount'))
    description = data.get('description', 'Purchase at school shop')
    payment_type = data.get('payment_type', 'student')
    
    # --- ADD THESE NEW VARIABLES ---
    friend_name = data.get('friend_name')
    friend_id = data.get('friend_id')
    parent_name = data.get('parent_name')
    parent_phone = data.get('parent_phone')
    # --- END OF NEW VARIABLES ---

    student = Student.query.filter_by(student_id=student_id_str).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    # --- SECURITY CHECK ---
    verified_student_id = session.get('upi_verified_student_id')
    verified_timestamp = session.get('upi_verified_timestamp')
    if not verified_student_id or verified_student_id != student.id:
        return jsonify({'error': 'UPI PIN not verified for this student.'}), 403
    # Check if verification happened in the last 60 seconds
    if not verified_timestamp or (datetime.now().timestamp() - verified_timestamp) > 60:
        return jsonify({'error': 'UPI verification timed out. Please try again.'}), 403
    # Clear the session variables so they can't be reused
    session.pop('upi_verified_student_id', None)
    session.pop('upi_verified_timestamp', None)
    # --- END SECURITY CHECK ---
    if student.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    try:
        # Deduct from student
        student.balance -= amount
        # Add to shopkeeper
        shopkeeper = Shopkeeper.query.get(session['shopkeeper_id'])
        shopkeeper.balance += amount
        
        # --- UPDATE THE TRANSACTION OBJECT CREATION ---
        transaction = Transaction(
            student_id=student.id,
            shopkeeper_id=shopkeeper.id,
            amount=-amount,
            description=f"{description} ({payment_type})",
            mode="shop_purchase", 
            status="completed",
            # Add the new fields
            friend_name=friend_name,
            friend_id=friend_id,
            parent_name=parent_name,
            parent_phone=parent_phone
        )
        # --- END OF UPDATE ---
        
        db.session.add(transaction)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Transaction successful! ₹{amount:.2f} deducted from student.',
            'new_balance': float(student.balance)
        })
    except Exception as e:
        db.session.rollback()
        # print(f"Error: {e}") # For debugging
        return jsonify({'error': 'Transaction failed'}), 500 
@app.route('/shopkeeper/dashboard')
def shopkeeper_dashboard():
    if 'shopkeeper_id' not in session:
        flash("Please log in as shopkeeper", "warning")
        return redirect(url_for('login'))

    shopkeeper = Shopkeeper.query.get(session['shopkeeper_id'])
    transactions = Transaction.query.filter_by(
        shopkeeper_id=shopkeeper.id
    ).order_by(Transaction.timestamp.desc()).all()
    
    balance = shopkeeper.balance if shopkeeper.balance else 0.0
    
    # Change template name to match your HTML file
    return render_template("shopkeeper_dashboard_modals.html", 
                         shopkeeper=shopkeeper, 
                         transactions=transactions, 
                         balance=balance)

@app.route('/shopkeeper/edit_password', methods=['POST'])
def shopkeeper_edit_password():
    if 'shopkeeper_id' not in session:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))

    shopkeeper = Shopkeeper.query.get(session['shopkeeper_id'])

    if not shopkeeper:
        flash('Shopkeeper not found', 'danger')
        return redirect(url_for('login'))
    
    current_password = request.form['current']
    new_password = request.form['new']
    confirm_password = request.form['confirm']

    # Validate current password
    if not check_password_hash(shopkeeper.password, current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('shopkeeper_dashboard'))

    # Validate new password match
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('shopkeeper_dashboard'))

    # Update password
    shopkeeper.password = generate_password_hash(new_password)
    db.session.commit()

    flash('Password updated successfully', 'success')
    return redirect(url_for('shopkeeper_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs('static/uploads/payment_proofs', exist_ok=True)
    app.run(debug=True)