import os
import random
import hashlib
import jwt
import resend
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_JbxrLj4k_NPAUnAHxMcpRVdx2Vf85gQUL")
JWT_SECRET = os.getenv("JWT_SECRET", "qarar_secret_key_change_in_production_2024")

resend.api_key = RESEND_API_KEY

# ==================== Fernet ====================
_fernet = None

def get_fernet():
    global _fernet
    if _fernet is None:
        key = os.getenv("ENCRYPTION_KEY", "")
        if not key:
            key = Fernet.generate_key().decode()
            print("[WARNING] No ENCRYPTION_KEY set — using temporary key")
        try:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            print(f"[ERROR] Invalid ENCRYPTION_KEY: {e}")
            _fernet = Fernet(Fernet.generate_key())
    return _fernet


def encrypt_message(text: str) -> str:
    return get_fernet().encrypt(text.encode()).decode()

def decrypt_message(encrypted: str) -> str:
    try:
        return get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return "[محتوى مشفر]"


# ==================== Password ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ==================== JWT ====================

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


# ==================== OTP ====================

def generate_otp() -> str:
    return str(random.randint(1000, 9999))


# ==================== Email via Resend ====================

def send_otp_email(email: str, otp: str, name: str = "") -> bool:
    try:
        greeting = f"أهلاً {name}" if name else "أهلاً"

        html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 40px 20px; background: #0a0d0f; color: #e8e4dc;">
            <div style="text-align: center; margin-bottom: 30px;">
                <span style="font-size: 40px;">🌙</span>
                <h1 style="color: #c9a84c; font-size: 28px; margin: 10px 0;">قرار</h1>
                <p style="color: #6b6760; font-size: 14px;">رفيقك حين تحتاج</p>
            </div>
            <div style="background: #161b20; border: 1px solid rgba(201,168,76,0.2); border-radius: 16px; padding: 30px; text-align: center;">
                <p style="color: #c8c4bc; font-size: 16px; margin-bottom: 8px;">{greeting}،</p>
                <p style="color: #8a8580; font-size: 14px; margin-bottom: 24px;">رمز التحقق الخاص بك:</p>
                <div style="background: rgba(201,168,76,0.1); border: 2px solid #c9a84c; border-radius: 12px; padding: 20px;">
                    <span style="font-size: 42px; font-weight: bold; color: #c9a84c; letter-spacing: 12px;">{otp}</span>
                </div>
                <p style="color: #6b6760; font-size: 13px; margin-top: 20px;">صالح لمدة 10 دقائق فقط</p>
            </div>
            <p style="color: #3a3835; font-size: 12px; text-align: center; margin-top: 24px;">إذا لم تطلب هذا الرمز، تجاهل هذا البريد.</p>
        </div>
        """

        params = {
            "from": "قرار <onboarding@resend.dev>",
            "to": [email],
            "subject": "قرار — رمز التحقق الخاص بك",
            "html": html,
        }

        resend.Emails.send(params)
        print(f"[EMAIL] OTP sent to {email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Error: {e}")
        return False


def send_password_reset_email(email: str, otp: str, name: str = "") -> bool:
    try:
        greeting = f"أهلاً {name}" if name else "أهلاً"

        html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 40px 20px; background: #0a0d0f; color: #e8e4dc;">
            <div style="text-align: center; margin-bottom: 30px;">
                <span style="font-size: 40px;">🌙</span>
                <h1 style="color: #c9a84c; font-size: 28px; margin: 10px 0;">قرار</h1>
                <p style="color: #6b6760; font-size: 14px;">رفيقك حين تحتاج</p>
            </div>
            <div style="background: #161b20; border: 1px solid rgba(201,168,76,0.2); border-radius: 16px; padding: 30px; text-align: center;">
                <p style="color: #c8c4bc; font-size: 16px; margin-bottom: 8px;">{greeting}،</p>
                <p style="color: #8a8580; font-size: 14px; margin-bottom: 24px;">رمز إعادة تعيين كلمة المرور:</p>
                <div style="background: rgba(201,168,76,0.1); border: 2px solid #c9a84c; border-radius: 12px; padding: 20px;">
                    <span style="font-size: 42px; font-weight: bold; color: #c9a84c; letter-spacing: 12px;">{otp}</span>
                </div>
                <p style="color: #6b6760; font-size: 13px; margin-top: 20px;">صالح لمدة 10 دقائق فقط</p>
            </div>
            <p style="color: #3a3835; font-size: 12px; text-align: center; margin-top: 24px;">إذا لم تطلب هذا، تجاهل هذا البريد.</p>
        </div>
        """

        params = {
            "from": "قرار <onboarding@resend.dev>",
            "to": [email],
            "subject": "قرار — إعادة تعيين كلمة المرور",
            "html": html,
        }

        resend.Emails.send(params)
        print(f"[EMAIL] Password reset sent to {email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Error: {e}")
        return False
