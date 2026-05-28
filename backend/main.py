from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional
import time
import re
import os
from dotenv import load_dotenv

load_dotenv()

import rag
import ai
import database
from auth import (
    hash_password, verify_password,
    create_token, verify_token,
    generate_otp, send_otp_email,
    send_password_reset_email
)

app = FastAPI(title="Qarar API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Auth Models ====================

class SignupRequest(BaseModel):
    email: str
    name: str
    age: int
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError("البريد الإلكتروني غير صحيح")
        return v.lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("الاسم يجب أن يكون حرفين على الأقل")
        return v.strip()

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v < 13 or v > 120:
            raise ValueError("العمر يجب أن يكون بين 13 و 120")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

class OTPRequest(BaseModel):
    email: str
    code: str

class ResendOTPRequest(BaseModel):
    email: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        return v


# ==================== Chat Models ====================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


# ==================== Auth Helper ====================

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="غير مصرح")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="الجلسة منتهية — يرجى تسجيل الدخول مجدداً")
    user = await database.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")
    return user


# ==================== Routes ====================

@app.get("/")
def root():
    return {"status": "Qarar v2 🌙", "version": "2.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}


# ---- Signup ----
@app.post("/auth/signup")
async def signup(req: SignupRequest):
    existing = await database.get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")

    user = await database.create_user(
        email=req.email,
        name=req.name,
        age=req.age,
        password_hash=hash_password(req.password)
    )

    # Auto-verify (OTP disabled temporarily)
    await database.verify_user_email(req.email)
    token = create_token(str(user["id"]), user["email"])

    return {
        "message": "تم إنشاء الحساب بنجاح",
        "token": token,
        "user": {
            "id": str(user["id"]),
            "name": user["name"],
            "email": user["email"]
        }
    }


# ---- Verify OTP ----
@app.post("/auth/verify-otp")
async def verify_otp_route(req: OTPRequest):
    valid = await database.verify_otp(req.email, req.code)
    if not valid:
        raise HTTPException(status_code=400, detail="الرمز غير صحيح أو منتهي الصلاحية")

    await database.verify_user_email(req.email)
    user = await database.get_user_by_email(req.email)
    token = create_token(str(user["id"]), user["email"])

    return {
        "message": "تم التحقق بنجاح",
        "token": token,
        "user": {
            "id": str(user["id"]),
            "name": user["name"],
            "email": user["email"]
        }
    }


# ---- Resend OTP ----
@app.post("/auth/resend-otp")
async def resend_otp(req: ResendOTPRequest):
    user = await database.get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="البريد الإلكتروني غير مسجل")

    otp = generate_otp()
    await database.save_otp(req.email, otp)
    sent = send_otp_email(req.email, otp, user.get("name", ""))

    return {"message": "تم إرسال رمز جديد", "otp_sent": sent}


# ---- Login ----
@app.post("/auth/login")
async def login(req: LoginRequest):
    user = await database.get_user_by_email(req.email.lower())
    if not user:
        raise HTTPException(status_code=401, detail="البريد أو كلمة المرور غير صحيحة")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="البريد أو كلمة المرور غير صحيحة")

    if not user["is_verified"]:
        otp = generate_otp()
        await database.save_otp(user["email"], otp)
        send_otp_email(user["email"], otp, user["name"])
        raise HTTPException(status_code=403, detail="الحساب غير مفعّل — تم إرسال رمز تحقق جديد")

    token = create_token(str(user["id"]), user["email"])

    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "name": user["name"],
            "email": user["email"],
            "subscription_status": user.get("subscription_status", "free")
        }
    }


# ---- Me ----
@app.get("/auth/me")
async def me(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    return {
        "id": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "subscription_status": user.get("subscription_status", "free")
    }


# ---- Forgot Password ----
@app.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    user = await database.get_user_by_email(req.email.lower())
    if not user:
        return {"message": "إذا كان البريد مسجلاً، ستصلك رسالة"}

    otp = generate_otp()
    await database.save_password_reset(req.email.lower(), otp)
    send_password_reset_email(req.email, otp, user.get("name", ""))

    return {"message": "إذا كان البريد مسجلاً، ستصلك رسالة"}


# ---- Reset Password ----
@app.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    valid = await database.verify_password_reset_code(req.email.lower(), req.code)
    if not valid:
        raise HTTPException(status_code=400, detail="الرمز غير صحيح أو منتهي الصلاحية")

    await database.update_user_password(req.email.lower(), hash_password(req.new_password))
    return {"message": "تم تغيير كلمة المرور بنجاح"}


# ---- Chat ----
@app.post("/chat")
async def chat(req: ChatRequest, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    user_id = str(user["id"])
    user_name = user["name"]

    history = []
    if req.conversation_id:
        history = await database.get_conversation_history(req.conversation_id)

    chunks = await rag.search_knowledge_base(req.message, top_k=5)

    reply = ai.generate_reply(
        message=req.message,
        context_chunks=chunks,
        history=history,
        user_name=user_name
    )

    conversation_id = req.conversation_id or f"conv_{user_id}_{int(time.time())}"

    await database.save_message(conversation_id, user_id, "user", req.message)
    await database.save_message(conversation_id, user_id, "assistant", reply)
    await database.update_last_seen(user_id)

    return {
        "reply": reply,
        "conversation_id": conversation_id,
        "sources": [
            {"book": c["book"], "author": c["author"], "score": c["score"]}
            for c in chunks[:3]
        ]
    }


@app.get("/conversations")
async def get_conversations(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    conversations = await database.get_user_conversations(str(user["id"]))
    return {"conversations": conversations}


@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, authorization: str = Header(None)):
    await get_current_user(authorization)
    messages = await database.get_conversation_history(conversation_id)
    return {"messages": messages}
