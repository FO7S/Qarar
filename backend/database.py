from supabase import create_client, Client
import os
from typing import List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from auth import encrypt_message, decrypt_message

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

_supabase: Optional[Client] = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ==================== Users ====================

async def create_user(email: str, name: str, age: int, password_hash: str) -> dict:
    sb = get_supabase()
    result = sb.table("users").insert({
        "email": email,
        "name": name,
        "age": age,
        "password_hash": password_hash,
        "is_verified": False
    }).execute()
    return result.data[0] if result.data else {}

async def get_user_by_email(email: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None

async def get_user_by_id(user_id: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else None

async def verify_user_email(email: str):
    sb = get_supabase()
    sb.table("users").update({"is_verified": True}).eq("email", email).execute()

async def update_last_seen(user_id: str):
    try:
        sb = get_supabase()
        sb.table("users").update({"last_seen": datetime.utcnow().isoformat()}).eq("id", user_id).execute()
    except:
        pass


# ==================== OTP ====================

async def save_otp(email: str, code: str):
    sb = get_supabase()
    sb.table("otp_codes").delete().eq("email", email).execute()
    sb.table("otp_codes").insert({
        "email": email,
        "code": code,
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        "used": False
    }).execute()

async def verify_otp(email: str, code: str) -> bool:
    sb = get_supabase()
    result = sb.table("otp_codes") \
        .select("*") \
        .eq("email", email) \
        .eq("code", code) \
        .eq("used", False) \
        .execute()

    if not result.data:
        return False

    otp = result.data[0]
    expires_at = datetime.fromisoformat(otp["expires_at"].replace("Z", "+00:00"))

    if datetime.now(expires_at.tzinfo) > expires_at:
        return False

    sb.table("otp_codes").update({"used": True}).eq("id", otp["id"]).execute()
    return True


# ==================== Messages (Encrypted) ====================

async def save_message(conversation_id: str, user_id: str, role: str, content: str) -> dict:
    try:
        sb = get_supabase()
        encrypted = encrypt_message(content)
        result = sb.table("messages").insert({
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content_encrypted": encrypted,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"[DB] save_message error: {e}")
        return {}

async def get_conversation_history(conversation_id: str) -> List[dict]:
    try:
        sb = get_supabase()
        result = sb.table("messages") \
            .select("role, content_encrypted, created_at") \
            .eq("conversation_id", conversation_id) \
            .order("created_at") \
            .execute()

        messages = []
        for msg in (result.data or []):
            messages.append({
                "role": msg["role"],
                "content": decrypt_message(msg["content_encrypted"]),
                "created_at": msg["created_at"]
            })
        return messages
    except Exception as e:
        print(f"[DB] get_conversation_history error: {e}")
        return []

async def get_user_conversations(user_id: str) -> List[dict]:
    try:
        sb = get_supabase()
        result = sb.table("messages") \
            .select("conversation_id, content_encrypted, created_at") \
            .eq("user_id", user_id) \
            .eq("role", "user") \
            .order("created_at") \
            .execute()

        conversations = {}
        for msg in (result.data or []):
            cid = msg["conversation_id"]
            if cid not in conversations:
                decrypted = decrypt_message(msg["content_encrypted"])
                title = decrypted[:65] + "..." if len(decrypted) > 65 else decrypted
                conversations[cid] = {
                    "id": cid,
                    "first_message": title,
                    "created_at": msg["created_at"]
                }
        return list(reversed(list(conversations.values())))
    except Exception as e:
        print(f"[DB] get_user_conversations error: {e}")
        return []


# ==================== Message Limits ====================

FREE_MESSAGE_LIMIT = 5
RESET_HOURS = 12

async def check_and_increment_message_limit(user_id: str, subscription_status: str) -> dict:
    if subscription_status == "active":
        return {"allowed": True, "remaining": 999, "reset_in_minutes": 0}

    try:
        from datetime import timezone
        sb = get_supabase()
        user = sb.table("users").select("free_messages_used, messages_reset_at").eq("id", user_id).execute()
        if not user.data:
            return {"allowed": False, "remaining": 0, "reset_in_minutes": 0}

        data = user.data[0]
        used = data.get("free_messages_used", 0) or 0
        reset_at_str = data.get("messages_reset_at")

        if reset_at_str:
            reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)

            if now >= reset_at + timedelta(hours=RESET_HOURS):
                sb.table("users").update({
                    "free_messages_used": 1,
                    "messages_reset_at": now.isoformat()
                }).eq("id", user_id).execute()
                return {"allowed": True, "remaining": FREE_MESSAGE_LIMIT - 1, "reset_in_minutes": 0}

            if used >= FREE_MESSAGE_LIMIT:
                time_left = (reset_at + timedelta(hours=RESET_HOURS)) - now
                minutes_left = int(time_left.total_seconds() / 60)
                return {"allowed": False, "remaining": 0, "reset_in_minutes": minutes_left}

            sb.table("users").update({"free_messages_used": used + 1}).eq("id", user_id).execute()
            return {"allowed": True, "remaining": FREE_MESSAGE_LIMIT - used - 1, "reset_in_minutes": 0}

        # No reset_at set yet
        sb.table("users").update({
            "free_messages_used": 1,
            "messages_reset_at": datetime.utcnow().isoformat()
        }).eq("id", user_id).execute()
        return {"allowed": True, "remaining": FREE_MESSAGE_LIMIT - 1, "reset_in_minutes": 0}

    except Exception as e:
        print(f"[DB] message limit error: {e}")
        return {"allowed": True, "remaining": FREE_MESSAGE_LIMIT, "reset_in_minutes": 0}


# ==================== Password Reset ====================

async def save_password_reset(email: str, code: str):
    sb = get_supabase()
    sb.table("password_resets").delete().eq("email", email).execute()
    sb.table("password_resets").insert({
        "email": email,
        "code": code,
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        "used": False
    }).execute()

async def verify_password_reset_code(email: str, code: str) -> bool:
    from datetime import timezone
    sb = get_supabase()
    result = sb.table("password_resets") \
        .select("*") \
        .eq("email", email) \
        .eq("code", code) \
        .eq("used", False) \
        .execute()

    if not result.data:
        return False

    otp = result.data[0]
    expires_at = datetime.fromisoformat(otp["expires_at"].replace("Z", "+00:00"))

    if datetime.now(timezone.utc) > expires_at:
        return False

    sb.table("password_resets").update({"used": True}).eq("id", otp["id"]).execute()
    return True

async def update_user_password(email: str, new_password_hash: str):
    sb = get_supabase()
    sb.table("users").update({"password_hash": new_password_hash}).eq("email", email).execute()
