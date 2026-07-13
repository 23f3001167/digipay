import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///student_bank.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL")
    SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD")
    
    # Email config for Super Admin notifications
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")  # novanine96@gmail.com
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # NovaNine@96
