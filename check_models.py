import os
import requests
from dotenv import load_dotenv

load_dotenv('backend/.env')
api_key = os.getenv('OPENAI_API_KEY')

response = requests.get(
    'https://api.openai.com/v1/models',
    headers={'Authorization': f'Bearer {api_key}'}
)

if response.status_code == 200:
    models = response.json()['data']
    realtime_models = [m['id'] for m in models if 'realtime' in m['id']]
    print("Realtime models available:")
    for rm in realtime_models:
        print(f" - {rm}")
else:
    print(f"Failed: {response.status_code} {response.text}")
