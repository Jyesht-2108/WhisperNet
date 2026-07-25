import os
import httpx
import asyncio
from dotenv import load_dotenv

env_path = r"c:\Users\Dell\pocketFM-Hacks\backend\.env"
load_dotenv(env_path)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def test_session():
    async with httpx.AsyncClient() as client:
        # TEST 1: Model INSIDE session
        payload1 = {
            "session": {
                "model": "gpt-4o-realtime-preview-2024-12-17",
                "instructions": "test 1"
            }
        }
        
        print("\n--- TEST 1: Model inside session ---")
        res1 = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=payload1
        )
        print("Status:", res1.status_code)
        print("Response:", res1.text)

        # TEST 2: Model AT ROOT
        payload2 = {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "modalities": ["audio", "text"],
            "instructions": "test 2"
        }
        
        print("\n--- TEST 2: Model at root ---")
        res2 = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=payload2
        )
        print("Status:", res2.status_code)
        print("Response:", res2.text)

if __name__ == "__main__":
    asyncio.run(test_session())
