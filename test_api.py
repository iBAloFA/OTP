import requests

# 1. Set your target URL 
# Change this to your public cloud URL (e.g., "https://onrender.com") after deploying!
BASE_URL = "http://127.0.0.1:8000"

# Target user for testing
TEST_EMAIL = "your-test-email@gmail.com" 

def test_otp_flow():
    print("--- 🩺 Testing Health Check ---")
    health_response = requests.get(f"{BASE_URL}/")
    print(f"Status: {health_response.status_code} | Response: {health_response.json()}\n")

    print("--- 📧 Requesting OTP ---")
    request_payload = {
        "email": TEST_EMAIL,
        "app_name": "RapidAPI Test Engine"
    }
    req_response = requests.post(f"{BASE_URL}/api/v1/otp/request", json=request_payload)
    print(f"Status: {req_response.status_code} | Response: {req_response.json()}\n")
    
    if req_response.status_code != 202:
        print("❌ OTP request failed. Check your terminal logs for SMTP/Twilio configuration errors.")
        return

    # Check your real email inbox or console log to find the 6-digit code!
    otp_code = input("👉 Enter the OTP code received in your inbox/logs: ")

    print("\n--- 🔐 Verifying OTP ---")
    verify_payload = {
        "identifier": TEST_EMAIL,
        "otp": otp_code
    }
    verify_response = requests.post(f"{BASE_URL}/api/v1/otp/verify", json=verify_payload)
    print(f"Status: {verify_response.status_code} | Response: {verify_response.json()}\n")
    
    if verify_response.json().get("success"):
        print("🎉 Success! Your API works seamlessly from end to end.")
    else:
        print("❌ Verification rejected. The code might have expired or is incorrect.")

if __name__ == "__main__":
    test_otp_flow()
