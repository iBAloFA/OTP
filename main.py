import os
import base64
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import asyncio
import httpx

import pyotp
import aiosmtplib
from email.mime.text import MIMEText
from twilio.rest import Client

from fastapi import FastAPI, HTTPException, status, Header, Depends
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------
# 1. CENTRALIZED CONFIGURATION & LOGGING
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rapidapi_analytics")

class AppSettings(BaseSettings):
    OTP_MASTER_SECRET: str = "RAPIDAPI_SECURE_BASE32_MASTER_KEY_DO_NOT_LEAK"
    EXPECTED_PROXY_SECRET: Optional[str] = None

    SMTP_HOST: str = "://gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASS: str = "your-app-specific-password"
    
    TWILIO_ACCOUNT_SID: str = "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    TWILIO_AUTH_TOKEN: str = "your_twilio_auth_token"
    TWILIO_PHONE_NUMBER: str = "+1234567890"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = AppSettings()
app = FastAPI(title="RapidAPI OTP Verification Service with Metrics Engine")

# ---------------------------------------------------------
# 2. IN-MEMORY CONCURRENT ANALYTICS STORAGE ENGINE
# ---------------------------------------------------------
class MetricsTracker:
    def __init__(self):
        self.total_requests = 0
        self.successful_verifications = 0
        self.failed_verifications = 0
        self.email_dispatches = 0
        self.sms_dispatches = 0
        self.gateway_errors = 0
        self.recent_errors = []
        self._lock = asyncio.Lock()

    async def log_request(self):
        async with self._lock:
            self.total_requests += 1

    async def log_dispatch(self, channel: str):
        async with self._lock:
            if channel == "email":
                self.email_dispatches += 1
            elif channel == "sms":
                self.sms_dispatches += 1

    async def log_verification(self, success: bool):
        async with self._lock:
            if success:
                self.successful_verifications += 1
            else:
                self.failed_verifications += 1

    async def log_error(self, endpoint: str, reason: str):
        async with self._lock:
            self.gateway_errors += 1
            error_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "reason": reason
            }
            # Keep only the last 20 runtime failures to manage memory
            self.recent_errors = [error_entry] + self.recent_errors[:19]

    async def get_snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            success_rate = 0.0
            total_verifications = self.successful_verifications + self.failed_verifications
            if total_verifications > 0:
                success_rate = round((self.successful_verifications / total_verifications) * 100, 2)

            return {
                "system_status": "operational",
                "counters": {
                    "total_api_calls": self.total_requests,
                    "email_sent_count": self.email_dispatches,
                    "sms_sent_count": self.sms_dispatches,
                    "delivery_failures": self.gateway_errors
                },
                "conversion_metrics": {
                    "approved_otps": self.successful_verifications,
                    "rejected_otps": self.failed_verifications,
                    "user_success_rate_percentage": f"{success_rate}%"
                },
                "recent_fault_logs": self.recent_errors
            }

metrics = MetricsTracker()

# ---------------------------------------------------------
# 3. DATA SCHEMAS & CRYPTO UTILITIES
# ---------------------------------------------------------
class RequestOTPModel(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")
    app_name: Optional[str] = "Your App"

class VerifyOTPModel(BaseModel):
    identifier: str
    otp: str

def get_user_secret(identifier: str) -> str:
    combined_str = f"{identifier}-{settings.OTP_MASTER_SECRET}"
    return base64.b32encode(combined_str.encode()).decode("utf-8")[:32]

# ---------------------------------------------------------
# 4. ASYNC DELIVERY CHANNELS WITH FAULT TELEMETRY
# ---------------------------------------------------------

# Update your settings model or place this configuration directly


# Update your settings model or fetch this variable directly from the environment strings
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_your_copied_api_key")

async def send_async_email(recipient: str, code: str, app_name: str):
    """Sends OTP using an unblockable HTTP Web API instead of traditional SMTP ports."""
    url = "https://resend.com"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        # Resend provides "onboarding@resend.dev" to let you test immediately without a custom domain!
        "from": f"{app_name} <onboarding@resend.dev>",
        "to": [recipient],
        "subject": f"[{app_name}] Security Verification Code",
        "html": f"<p>Your security code is <strong>{code}</strong>. Valid for 5 minutes.</p>"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            # Checked status verification fix applied below:
            if response.status_code not in:
                err_msg = f"HTTP Email API error: {response.text}"
                logger.error(err_msg)
                await metrics.log_error("/api/v1/otp/request", err_msg)
                raise HTTPException(status_code=503, detail="Email service temporary failure.")
            
            await metrics.log_dispatch("email")
        except Exception as e:
            logger.error(f"Network error trying to contact Email API: {e}")
            raise HTTPException(status_code=503, detail="Internal gateway routing error.")



async def send_twilio_sms_async(recipient_phone: str, code: str, app_name: str):
    def _send():
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"Your verification code for {app_name} is: {code}. Valid for 5 minutes.",
            from_=settings.TWILIO_PHONE_NUMBER, to=recipient_phone
        )
    try:
        await asyncio.to_thread(_send)
        await metrics.log_dispatch("sms")
    except Exception as e:
        err_msg = f"SMS gateway exception: {str(e)}"
        logger.error(f"SMS failure to {recipient_phone}: {e}")
        await metrics.log_error("/api/v1/otp/request", err_msg)
        raise HTTPException(status_code=503, detail="Internal cellular carrier delivery failure.")

def verify_rapidapi_proxy(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    if settings.EXPECTED_PROXY_SECRET and x_rapidapi_proxy_secret != settings.EXPECTED_PROXY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct execution blocked. This service must be consumed via RapidAPI Marketplace."
        )

# ---------------------------------------------------------
# 5. MARKETPLACE API ENDPOINTS WITH ANALYTICS HOOKS
# ---------------------------------------------------------
@app.get("/", status_code=status.HTTP_200_OK)
async def health():
    await metrics.log_request()
    return {"status": "online", "description": "RapidAPI OTP Microservice Core"}

@app.post("/api/v1/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(data: RequestOTPModel, _ = Depends(verify_rapidapi_proxy)):
    await metrics.log_request()
    
    if not data.email and not data.phone_number:
        await metrics.log_error("/api/v1/otp/request", "Client missing body details.")
        raise HTTPException(status_code=400, detail="Missing parameter payload: Provide email or phone_number.")
    
    channels_dispatched = []
    
    if data.email:
        totp = pyotp.TOTP(get_user_secret(data.email), interval=300)
        await send_async_email(data.email, totp.now(), data.app_name)
        channels_dispatched.append("email")
        
    if data.phone_number:
        totp = pyotp.TOTP(get_user_secret(data.phone_number), interval=300)
        await send_twilio_sms_async(data.phone_number, totp.now(), data.app_name)
        channels_dispatched.append("sms")
        
    return {
        "success": True, 
        "message": f"Verification token dispatched via {', '.join(channels_dispatched)}.",
        "verified_channels": channels_dispatched
    }

@app.post("/api/v1/otp/verify", status_code=status.HTTP_200_OK)
async def verify_otp(data: VerifyOTPModel, _ = Depends(verify_rapidapi_proxy)):
    await metrics.log_request()
    totp = pyotp.TOTP(get_user_secret(data.identifier), interval=300)
    
    if not totp.verify(data.otp):
        await metrics.log_verification(success=False)
        return {
            "success": False,
            "status": "rejected",
            "reason": "The submitted code is invalid, wrong, or has timed out."
        }
        
    await metrics.log_verification(success=True)
    return {
        "success": True,
        "status": "approved",
        "message": "Identity successfully confirmed."
    }

# ---------------------------------------------------------
# 6. ADMINISTRATIVE BILLING & TELEMETRY MONITOR ENDPOINT
# ---------------------------------------------------------
@app.get("/api/v1/admin/telemetry", status_code=status.HTTP_200_OK)
async def get_runtime_metrics(admin_key: Optional[str] = Header(None)):
    """Secret dashboard endpoint to review system performance and health logs."""
    # Set a highly secure admin key pass inside environment strings to protect your metrics
    secured_admin_pass = os.getenv("ADMIN_DASHBOARD_SECRET", "DEFAULT_INSECURE_METRICS_PASSPHRASE")
    
    if admin_key != secured_admin_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Denied: Invalid administrative monitoring passphrase header."
        )
        
    return await metrics.get_snapshot()
