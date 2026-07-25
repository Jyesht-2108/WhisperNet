import os
import asyncio
import websockets
import json
from dotenv import load_dotenv

env_path = r"c:\Users\Dell\pocketFM-Hacks\backend\.env"
load_dotenv(env_path)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def test_websocket():
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2.1"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }
    
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            print("Connected! Waiting for session.created...")
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print("RECV:", data["type"])
                if data["type"] == "session.created":
                    break
            
            update_event = {
              "type": "session.update",
              "session": {
                "instructions": "test instructions",
                "turn_detection": {
                  "type": "server_vad",
                  "threshold": 0.5,
                  "prefix_padding_ms": 300,
                  "silence_duration_ms": 500,
                },
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
              },
            }
            print("\nSending session.update:", json.dumps(update_event, indent=2))
            await ws.send(json.dumps(update_event))
            
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print("RECV:", data["type"])
                if data["type"] == "error":
                    print("ERROR:", json.dumps(data, indent=2))
                    break
                if data["type"] == "session.updated":
                    print("SUCCESS: Session updated!")
                    break
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    asyncio.run(test_websocket())
