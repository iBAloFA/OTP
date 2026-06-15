# 🚀 Universal OTP Verification Engine (RapidAPI Ready)

A high-performance, stateless, and secure One-Time Password (OTP) microservice built with **FastAPI** and **PyOTP**. Designed specifically to handle multi-channel (Asynchronous Email & Twilio SMS) user validation workflows for websites and mobile registration systems.

This architecture is optimized out-of-the-box for production hosting on cloud environments (Render, Railway, AWS) and seamless commercialization on marketplaces like **RapidAPI**.

---

## ✨ Core Engineering Highlights

*   **Stateless & DB-Independent Token Generation**: Uses Time-Based One-Time Password (TOTP) cryptographic algorithms via PyOTP. Eliminates database storage bottlenecks and lookups for active validation sessions.
*   **Asynchronous Multi-Channel Dispatch**: Out-of-the-box integration with standard live SMTP engines (`aiosmtplib`) and cellular communication portals via the Twilio SDK.
*   **RapidAPI Ready Proxy Layer**: Features built-in authentication proxy header enforcement checks to safeguard your cloud architecture from bad actors trying to bypass marketplace monetized endpoints.
*   **Robust Data Quality Enforcement**: Fully typed parameter payloads structured via Pydantic schemas, utilizing standard E.164 phone formats and validated email structures.

---

## 🛠️ Architecture & Tech Stack

*   **Framework**: FastAPI (Asynchronous Python Web Framework)
*   **Cryptography Engine**: PyOTP (RFC 6238 TOTP tokens)
*   **Email Engine**: `aiosmtplib` (Non-blocking SMTP operations)
*   **SMS Gateway**: Twilio Python Helper Library
*   **Configuration Security**: Pydantic Settings (Environment Variable decoupling)

---

## ⚙️ Quick Start & Local Setup

### 1. Clone the Codebase
```bash
git clone https://github.com
cd your-repo-name
```

### 2. Configure Virtual Environment & Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Establish Runtime Environment Configurations
Create a local `.env` file in the project root directory:
```text
OTP_MASTER_SECRET=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP
SMTP_HOST=://gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-google-app-specific-password
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
EXPECTED_PROXY_SECRET=OptionalRapidAPIProxyKeyHere
```

### 4. Execute the Application Instance
```bash
uvicorn main:app --reload
```
Once initialized, access the auto-generated documentation suite at: **`http://127.0.0`**

---

## 🌐 API Endpoint Reference Map

### 🟢 1. Health Status Verification
*   **HTTP Verb**: `GET`
*   **Path**: `/`
*   **Response Payload**:
    ```json
    { "status": "online", "description": "RapidAPI OTP Microservice Core" }
    ```

### 🔵 2. Request OTP Code Dispatch
*   **HTTP Verb**: `POST`
*   **Path**: `/api/v1/otp/request`
*   **Request Sample Payload**:
    ```json
    {
      "email": "user@example.com",
      "phone_number": "+14155552671",
      "app_name": "SaaS Platform"
    }
    ```

### 🟡 3. Execute OTP Cryptographic Verification
*   **HTTP Verb**: `POST`
*   **Path**: `/api/v1/otp/verify`
*   **Request Sample Payload**:
    ```json
    {
      "identifier": "user@example.com",
      "otp": "123456"
    }
    ```

---

## 🚀 Cloud Deployment Architecture

This microservice maps configurations natively to runtime parameters. It contains pre-written production `Procfile` structures ready to be plugged into automated pipeline integrations across cloud providers:

*   **Render**: Connect repo -> Define Python Runtime -> Bind variables -> Set start command as `uvicorn main:app --host 0.0.0.0 --port $PORT`
*   **Railway**: Connect repo -> Auto-detects dependencies -> Bind variables -> Public domain automatically provisioned.

---

## 💳 RapidAPI Commercialization
When listing this on the RapidAPI marketplace dashboard:
1. Access `http://127.0.0.1` locally and save the spec file.
2. Create your project on RapidAPI Studio using the saved **OpenAPI Document**.
3. Set your live deployed cloud URL as the base routing target under gateway profiles.
4. Establish your desired monetization tiers and subscription tiers directly on RapidAPI.
