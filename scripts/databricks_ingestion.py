# Databricks Ingestion Notebook Script
# 
# Instructions:
# 1. Create a new Python notebook in your Databricks workspace.
# 2. Paste this entire script into the notebook.
# 3. Attach a compute cluster (Serverless is fine) and run the cell.
# 
# This script will insert sample Solo Leveling lore into your empty Delta table.
# Once inserted, the Databricks Vector Search will automatically sync the data!

import uuid
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, ArrayType

# Initialize Spark session
spark = SparkSession.builder.getOrCreate()

# Ensure we are using the correct catalog and schema
spark.sql("USE CATALOG whispernet")
spark.sql("USE SCHEMA rag")

print("Connected to Unity Catalog: whispernet.rag")

# Sample Solo Leveling Lore Data
# episode_index represents the timeline. The AI will strictly filter out any data 
# where episode_index > the user's current live playback position to avoid spoilers!
sample_lore = [
    {
        "id": str(uuid.uuid4()),
        "text": "Sung Jinwoo was known as the 'Weakest Hunter of All Mankind'. He was an E-rank hunter who struggled to survive even in the lowest-level D-rank dungeons.",
        "episode_index": 1,
        "character_tags": ["Sung Jinwoo", "Hunter"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "The Double Dungeon incident occurred inside a D-rank gate. Jinwoo's party found a hidden temple with massive stone statues. The statues started moving and killing the hunters when they failed to follow the 'Commandments of the Carthenon Temple'.",
        "episode_index": 2,
        "character_tags": ["Sung Jinwoo", "Architect", "Statues"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "In his dying moments on the altar of the Double Dungeon, Jinwoo completed the secret quest 'Courage of the Weak' and accepted the offer to become a 'Player'.",
        "episode_index": 2,
        "character_tags": ["Sung Jinwoo", "System"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "Jinwoo woke up in a hospital bed with a mysterious video game-like System interface floating in front of him, assigning him daily quests.",
        "episode_index": 3,
        "character_tags": ["Sung Jinwoo", "System"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "Failure to complete the System's daily quest (100 push-ups, 100 sit-ups, 100 squats, 10km run) results in a penalty quest where Jinwoo is teleported to a desert full of giant centipedes for 4 hours.",
        "episode_index": 3,
        "character_tags": ["Sung Jinwoo", "System"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "Jinwoo obtains a magical key that opens an Instance Dungeon inside a subway station, where he fights Steel-Fanged Lycans and levels up for the first time.",
        "episode_index": 4,
        "character_tags": ["Sung Jinwoo", "System", "Monsters"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "The title 'Shadow Monarch' is an immensely powerful class that allows the user to extract the shadows of dead enemies and turn them into loyal shadow soldiers.",
        "episode_index": 12,  # Spoiler for later!
        "character_tags": ["Sung Jinwoo", "Shadow Monarch", "System"]
    },
    {
        "id": str(uuid.uuid4()),
        "text": "Igris the Bloodred is a powerful knight boss that Jinwoo defeats during his job change quest. Igris becomes Jinwoo's first major shadow soldier.",
        "episode_index": 15,  # Spoiler for later!
        "character_tags": ["Sung Jinwoo", "Igris", "Shadows"]
    }
]

# Define the schema matching your existing Delta Table
schema = StructType([
    StructField("id", StringType(), False),
    StructField("text", StringType(), True),
    StructField("episode_index", IntegerType(), True),
    StructField("character_tags", ArrayType(StringType()), True)
])

# Create a DataFrame from the sample data
df = spark.createDataFrame(sample_lore, schema)

print(f"Prepared DataFrame with {df.count()} lore chunks.")

# Insert the data into the Delta table
print("Writing data to whispernet.rag.solo_leveling_lore...")
df.write.format("delta").mode("append").saveAsTable("whispernet.rag.solo_leveling_lore")

print("✅ Data successfully ingested!")
print("Databricks Vector Search will now automatically detect the new data and sync it to your index (solo_leveling_index). This usually takes 1-3 minutes.")
