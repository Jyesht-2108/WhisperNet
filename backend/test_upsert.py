import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.services.databricks_client import DatabricksClient
from app.config import get_settings

async def main():
    # reload settings so the env changes take effect
    import importlib
    import app.config
    importlib.reload(app.config)
    
    client = DatabricksClient()
    print("Attempting to insert a test transcription chunk via Databricks SQL...")
    success = await client.upsert_lore(
        text="[LIVE TRANSCRIPT TEST] Jake was walking down the hall when he suddenly heard a loud noise.",
        episode_index=1
    )
    if success:
        print("SQL Insert succeeded!")
    else:
        print("SQL Insert failed!")

if __name__ == "__main__":
    asyncio.run(main())
