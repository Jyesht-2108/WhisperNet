import os
import httpx
import asyncio
from dotenv import load_dotenv

env_path = r"c:\Users\Dell\pocketFM-Hacks\backend\.env"
load_dotenv(env_path)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def test_webrtc_calls():
    async with httpx.AsyncClient() as client:
        print("1. Getting token for gpt-realtime-2...")
        token_res = await client.post(
            "https://api.openai.com/v1/realtime/client_secrets",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "session": {
                    "type": "realtime",
                    "model": "gpt-4o-realtime-preview-2024-12-17",
                    "instructions": "test"
                }
            }
        )
        print("Token Status:", token_res.status_code)
        if token_res.status_code != 200:
            print("Failed to get token:", token_res.text)
            return
            
        token_data = token_res.json()
        ephemeral_token = token_data.get("value")
        
        print(f"2. Got token: {ephemeral_token[:15]}... Sending SDP offer to /v1/realtime/calls")
        
        # Dummy SDP just to see if it rejects the model or the SDP
        dummy_sdp = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\n"
        
        call_res = await client.post(
            "https://api.openai.com/v1/realtime/calls",
            headers={
                "Authorization": f"Bearer {ephemeral_token}",
                "Content-Type": "application/sdp"
            },
            content=dummy_sdp
        )
        print("Call Status:", call_res.status_code)
        print("Call Response:", call_res.text)

if __name__ == "__main__":
    asyncio.run(test_webrtc_calls())
