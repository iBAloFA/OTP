import os
import base64
import logging
from typing import Optional

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
logger = logging.getLogger("rapidapi_otp")

class AppSettings(BaseSettings):
    # Production application security 
    OTP_MASTER_SECRET: str = "RAPIDAPI_SECURE_BASE32_MASTER_KEY_DO_NOT_LEAK"
    
    # RapidAPI Proxy Validation Secret (Optional security layer to verify requests come *only* from RapidAPI)
    # RapidAPI passes a unique header "X-RapidAPI-Proxy-Secret" if configured in their dashboard.
    EXPECTED_PROXY_SECRET: Optional[str] = None

    # Live Gateway Configurations
    SMTP_HOST: str = "://gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASS: str = "your-app-specific-password"
    
    TWILIO_ACCOUNT_SID: str = "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    TWILIO_AUTH_TOKEN: str = "your_twilio_auth_token"
    TWILIO_PHONE_NUMBER: str = "+1234567890"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = AppSettings()
app = FastAPI(title="RapidAPI OTP Verification Service")

# ---------------------------------------------------------
# 2. DATA SCHEMAS & CRYPTO UTILITIES
# ---------------------------------------------------------
class RequestOTPModel(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")
    app_name: Optional[str] = "Your App"  # Allows developers to customize the SMS/Email template text

class VerifyOTPModel(BaseModel):
    identifier: str  # Email or Mobile format
    otp: str

def get_user_secret(identifier: str) -> str:
    combined_str = f"{identifier}-{settings.OTP_MASTER_SECRET}"
    return base64.b32encode(combined_str.encode()).decode("utf-8")[:32]

# ---------------------------------------------------------
# 3. ASYNC DELIVERY CHANNELS
# ---------------------------------------------------------
async def send_async_email(recipient: str, code: str, app_name: str):
    message = MIMEText(f"Your verification code for {app_name} is: {code}.\nIt will expire in 5 minutes.")
    message["From"] = settings.SMTP_USER
    message["To"] = recipient
    message["Subject"] = f"[{app_name}] Security Verification Code"
    
    try:
        await aiosmtplib.send(
            message, hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
            username=settings.SMTP_USER, password=settings.SMTP_PASS,
            start_tls=True if settings.SMTP_PORT == 587 else False,
            use_tls=True if settings.SMTP_PORT == 464 else False,
        )
    except Exception as e:
        logger.error(f"Mail failure to {recipient}: {e}")
        raise HTTPException(status_code=503, detail="Internal mail infrastructure delivery failure.")

async def send_twilio_sms_async(recipient_phone: str, code: str, app_name: str):
    import asyncio
    def _send():
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"Your verification code for {app_name} is: {code}. Valid for 5 minutes.",
            from_=settings.TWILIO_PHONE_NUMBER, to=recipient_phone
        )
    try:
        await asyncio.to_thread(_send)
    except Exception as e:
        logger.error(f"SMS failure to {recipient_phone}: {e}")
        raise HTTPException(status_code=503, detail="Internal cellular carrier delivery failure.")

# ---------------------------------------------------------
# 4. HOOK TO VERIFY INCOMING RAPIDAPI PROXY SECURITY (RECOMMENDED)
# ---------------------------------------------------------
def verify_rapidapi_proxy(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    """Blocks bad actors who find your direct backend URL and try to bypass RapidAPI monetization."""
    if settings.EXPECTED_PROXY_SECRET and x_rapidapi_proxy_secret != settings.EXPECTED_PROXY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct execution blocked. This service must be consumed via RapidAPI Marketplace."
        )

# ---------------------------------------------------------
# 5. MARKETPLACE API ENDPOINTS
# ---------------------------------------------------------
@app.get("/", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "online", "description": "RapidAPI OTP Microservice Core"}

@app.post("/api/v1/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(
    data: RequestOTPModel, 
    # Capture RapidAPI default analytics parameters directly from header metadata if needed
    x_rapidapi_user: Optional[str] = Header(None), 
    _ = Depends(verify_rapidapi_proxy)
):
    if not data.email and not data.phone_number:
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
    totp = pyotp.TOTP(get_user_secret(data.identifier), interval=300)
    
    if not totp.verify(data.otp):
        return {
            "success": False,
            "status": "rejected",
            "reason": "The submitted code is invalid, wrong, or has timed out."
        }
        
    return {
        "success": True,
        "status": "approved",
        "message": "Identity successfully confirmed."
    }
