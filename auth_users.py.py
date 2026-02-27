"""
Revoda — User Authentication & Account Management API
Handles: Registration, Login, Email Verification, Password Reset, Profile

Add these routes to your main.py:
  app.include_router(auth_router)
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator, EmailStr
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
import asyncpg, uuid, secrets, hashlib
import bcrypt
from jose import jwt, JWTError
import os, re

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-in-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week sessions


# ── Pydantic Models ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    # Personal details
    first_name: str
    last_name: str
    email: str
    phone: str
    password: str

    # Organisation details
    org_name: str
    org_type: Literal["cso", "media", "academic", "legal", "inec"]
    state: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("first_name", "last_name", "org_name")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("This field cannot be empty")
        return v.strip()


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    org_name: Optional[str] = None
    state: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    org_name: str
    org_type: str
    state: str
    status: str             # pending | approved | suspended
    role: str               # partner | admin
    api_token_prefix: str   # first 12 chars only — never expose full token
    created_at: datetime
    approved_at: Optional[datetime] = None
    reports_count: int = 0


# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def create_jwt(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire, "iat": datetime.now(timezone.utc)},
        SECRET_KEY, algorithm=ALGORITHM
    )

def generate_api_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store only the hash."""
    raw = "rvd_live_" + secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request = None
) -> dict:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    db = request.app.state.db
    async with db.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND status != 'suspended'", user_id
        )
    if not user:
        raise HTTPException(401, "Account not found or suspended")
    return dict(user)

async def require_approved(user = Depends(get_current_user)):
    if user["status"] != "approved":
        raise HTTPException(403, "Your account is pending approval by EiE Nigeria")
    return user

async def require_admin(user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user


# ── ROUTES ────────────────────────────────────────────────────────────────────

@auth_router.post("/register", status_code=201)
async def register(body: RegisterRequest, background_tasks: BackgroundTasks, request=None):
    """
    Register a new partner organisation account.
    Account starts as 'pending' — EiE Nigeria must approve it.
    """
    db = request.app.state.db

    async with db.acquire() as conn:
        # Check if email already exists
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", body.email
        )
        if existing:
            raise HTTPException(409, "An account with this email already exists")

        user_id = str(uuid.uuid4())
        pw_hash = hash_password(body.password)
        raw_token, token_hash = generate_api_token()

        # Create verification token (expires in 48h)
        verify_token = secrets.token_urlsafe(32)

        await conn.execute("""
            INSERT INTO users (
                id, email, password_hash, first_name, last_name,
                org_name, org_type, phone, state,
                status, role, api_token_hash, api_token_prefix,
                email_verify_token, created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending','partner',$10,$11,$12,NOW())
        """,
            user_id, body.email, pw_hash,
            body.first_name, body.last_name,
            body.org_name, body.org_type, body.phone, body.state,
            token_hash, raw_token[:12] + "...",
            verify_token
        )

    # Send verification email (background task)
    background_tasks.add_task(
        send_verification_email,
        email=body.email,
        name=body.first_name,
        org=body.org_name,
        token=verify_token,
        user_id=user_id
    )

    # Notify EiE Nigeria admin of new registration
    background_tasks.add_task(
        notify_admin_new_registration,
        name=f"{body.first_name} {body.last_name}",
        org=body.org_name,
        org_type=body.org_type,
        email=body.email
    )

    return {
        "message": "Account created successfully. Please check your email to verify your address. EiE Nigeria will review and approve your account within 24–48 hours.",
        "user_id": user_id,
        "application_id": f"RVD-APP-{user_id[:8].upper()}",
        "status": "pending"
    }


@auth_router.post("/login")
async def login(body: LoginRequest, request=None):
    """
    Log in and receive a JWT access token.
    Pending accounts can log in but have limited access.
    """
    db = request.app.state.db

    async with db.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1", body.email.lower().strip()
        )

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    if user["status"] == "suspended":
        raise HTTPException(403, "Your account has been suspended. Contact EiE Nigeria.")

    # Update last login
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1", user["id"]
        )

    token = create_jwt(str(user["id"]), user["role"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_EXPIRE_HOURS * 3600,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "org_name": user["org_name"],
            "org_type": user["org_type"],
            "status": user["status"],
            "role": user["role"],
        }
    }


@auth_router.get("/me", response_model=UserResponse)
async def get_me(request=None, credentials = Depends(security)):
    """Get current user's profile and stats."""
    user = await get_current_user(credentials, request)
    db = request.app.state.db

    async with db.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM incidents WHERE source_partner = $1",
            user["org_name"]
        )

    return UserResponse(
        **{k: v for k, v in user.items() if k in UserResponse.model_fields},
        reports_count=count or 0
    )


@auth_router.patch("/profile")
async def update_profile(body: UpdateProfileRequest, request=None, credentials = Depends(security)):
    """Update user profile details."""
    user = await get_current_user(credentials, request)
    db = request.app.state.db

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    params = [user["id"]] + list(updates.values())

    async with db.acquire() as conn:
        await conn.execute(
            f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = $1",
            *params
        )

    return {"message": "Profile updated successfully"}


@auth_router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request=None, credentials = Depends(security)):
    """Change password for logged-in user."""
    user = await get_current_user(credentials, request)

    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")

    db = request.app.state.db
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            hash_password(body.new_password), user["id"]
        )

    return {"message": "Password changed successfully"}


@auth_router.post("/forgot-password")
async def forgot_password(body: PasswordResetRequest, background_tasks: BackgroundTasks, request=None):
    """Send password reset email."""
    db = request.app.state.db
    async with db.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", body.email.lower())

    # Always return success (don't reveal if email exists)
    if user:
        reset_token = secrets.token_urlsafe(32)
        async with db.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET pw_reset_token = $1, pw_reset_expires = NOW() + INTERVAL '2 hours'
                WHERE id = $2
            """, reset_token, user["id"])

        background_tasks.add_task(
            send_password_reset_email,
            email=user["email"],
            name=user["first_name"],
            token=reset_token
        )

    return {"message": "If an account with that email exists, a password reset link has been sent."}


@auth_router.post("/reset-password")
async def reset_password(body: PasswordResetConfirm, request=None):
    """Complete password reset with token from email."""
    db = request.app.state.db
    async with db.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT * FROM users
            WHERE pw_reset_token = $1
            AND pw_reset_expires > NOW()
        """, body.token)

    if not user:
        raise HTTPException(400, "Invalid or expired reset token. Please request a new one.")

    async with db.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET password_hash = $1, pw_reset_token = NULL, pw_reset_expires = NULL, updated_at = NOW()
            WHERE id = $2
        """, hash_password(body.new_password), user["id"])

    return {"message": "Password reset successfully. You can now log in with your new password."}


@auth_router.get("/verify-email/{token}")
async def verify_email(token: str, request=None):
    """Verify email address from link in welcome email."""
    db = request.app.state.db
    async with db.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email_verify_token = $1", token
        )

    if not user:
        raise HTTPException(400, "Invalid verification link")

    async with db.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET email_verified = TRUE, email_verify_token = NULL, updated_at = NOW()
            WHERE id = $1
        """, user["id"])

    return {"message": "Email verified successfully. Your account is now pending approval by EiE Nigeria."}


@auth_router.post("/regenerate-token")
async def regenerate_api_token(request=None, credentials = Depends(security)):
    """Generate a new API token (invalidates the old one)."""
    user = await require_approved(await get_current_user(credentials, request))
    raw_token, token_hash = generate_api_token()

    db = request.app.state.db
    async with db.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET api_token_hash = $1, api_token_prefix = $2, updated_at = NOW()
            WHERE id = $3
        """, token_hash, raw_token[:12] + "...", user["id"])

    return {
        "api_token": raw_token,
        "warning": "Save this token now — it will not be shown again."
    }


# ── ADMIN ROUTES ───────────────────────────────────────────────────────────────

@auth_router.get("/admin/users")
async def list_users(request=None, credentials = Depends(security)):
    """Admin: list all registered users."""
    await require_admin(await get_current_user(credentials, request))
    db = request.app.state.db
    async with db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, email, first_name, last_name, org_name, org_type,
                   status, role, created_at, last_login_at, email_verified
            FROM users ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]


@auth_router.patch("/admin/users/{user_id}/approve")
async def approve_user(user_id: str, request=None, credentials = Depends(security)):
    """Admin: approve a pending partner account."""
    admin = await require_admin(await get_current_user(credentials, request))
    db = request.app.state.db

    async with db.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        if not user:
            raise HTTPException(404, "User not found")
        await conn.execute("""
            UPDATE users SET status = 'approved', approved_at = NOW(), approved_by = $1 WHERE id = $2
        """, admin["email"], user_id)

    # Send approval notification email
    await send_approval_email(user["email"], user["first_name"], user["org_name"])

    return {"message": f"Account for {user['org_name']} approved successfully"}


@auth_router.patch("/admin/users/{user_id}/suspend")
async def suspend_user(user_id: str, request=None, credentials = Depends(security)):
    """Admin: suspend an account."""
    await require_admin(await get_current_user(credentials, request))
    db = request.app.state.db
    async with db.acquire() as conn:
        await conn.execute("UPDATE users SET status = 'suspended' WHERE id = $1", user_id)
    return {"message": "Account suspended"}


# ── EMAIL FUNCTIONS (integrate with SendGrid) ──────────────────────────────────

async def send_verification_email(email: str, name: str, org: str, token: str, user_id: str):
    verify_url = f"https://revoda.eienigeria.org/api/v1/auth/verify-email/{token}"
    print(f"[EMAIL] Verification to {email}: {verify_url}")
    # TODO: integrate with SendGrid
    # subject = f"Verify your Revoda account — {org}"
    # body = f"Hi {name},\n\nClick to verify: {verify_url}\n\nEiE Nigeria"
    # await _send_via_sendgrid(email, subject, body)


async def send_password_reset_email(email: str, name: str, token: str):
    reset_url = f"https://revoda.eienigeria.org/reset-password?token={token}"
    print(f"[EMAIL] Password reset to {email}: {reset_url}")


async def send_approval_email(email: str, name: str, org: str):
    print(f"[EMAIL] Approval notification to {email} for {org}")
    # Include their API token and dashboard link


async def notify_admin_new_registration(name: str, org: str, org_type: str, email: str):
    print(f"[ADMIN ALERT] New registration: {name} from {org} ({org_type}) — {email}")
