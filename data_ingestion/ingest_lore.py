import uuid
import re
import os
from typing import Iterator, List
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, ArrayType

def chunk_text(text: str, min_size: int = 500, max_size: int = 800, overlap: int = 120) -> Iterator[str]:
    """
    A robust custom Python generator that splits text into chunks.
    Target chunk size is between min_size and max_size characters, 
    with an exact overlap of `overlap` characters.
    Attempts to break at word boundaries (spaces) when possible.
    """
    start = 0
    text_length = len(text)
    
    if text_length <= max_size:
        yield text.strip()
        return

    while start < text_length:
        end = start + max_size
        
        if end >= text_length:
            yield text[start:text_length].strip()
            break
            
        # Try to find a space to break at to avoid cutting words in half.
        # We look backwards from `end` down to `start + min_size`.
        break_point = end
        while break_point > start + min_size and text[break_point] != ' ':
            break_point -= 1
            
        # If we couldn't find a space in the preferred window, just hard break at max_size
        if break_point == start + min_size:
            break_point = end
            
        yield text[start:break_point].strip()
        
        # Advance the start pointer, ensuring exactly `overlap` characters overlap 
        # with the current chunk's end.
        start = break_point - overlap


def mock_extract_episode_index(chunk: str, source_filename: str = "") -> int:
    """
    Mock logic to extract an episode index from the source text.
    Maps known source files to episode indices. Replace with actual
    extraction logic once the full episode-tagged corpus is available.
    """
    # Map source files to episode indices for now
    episode_map = {
        "story1.txt": 1,
        "story2.txt": 2,
        "story3.txt": 3,
    }
    return episode_map.get(source_filename, 1)


# ── Character detection patterns ──
# Covers both Solo Leveling lore AND the story1.txt characters.
_CHARACTER_PATTERNS = [
    # Story1 characters
    (re.compile(r'\bjake\b', re.IGNORECASE), "Jake"),
    (re.compile(r'\bjacob\b', re.IGNORECASE), "Jacob"),
    (re.compile(r'\bbertram\b', re.IGNORECASE), "Bertram"),
    (re.compile(r'\bcaroline\b', re.IGNORECASE), "Caroline"),
    (re.compile(r'\bjoanna\b', re.IGNORECASE), "Joanna"),
    (re.compile(r'\bmike\b', re.IGNORECASE), "Mike"),
    # Solo Leveling characters
    (re.compile(r'\bjin-?woo\b', re.IGNORECASE), "Sung Jinwoo"),
    (re.compile(r'\bsystem\b', re.IGNORECASE), "System"),
    (re.compile(r'\barchitect\b', re.IGNORECASE), "Architect"),
    (re.compile(r'\bigris\b', re.IGNORECASE), "Igris"),
    (re.compile(r'\bjin-?ho\b', re.IGNORECASE), "Yoo Jin-Ho"),
]


def extract_character_tags(chunk: str) -> List[str]:
    """
    Extract character entity tags from a chunk using regex patterns.
    Returns a deduplicated list of character names found.
    """
    tags = []
    for pattern, name in _CHARACTER_PATTERNS:
        if pattern.search(chunk):
            tags.append(name)
    return tags if tags else ["Unknown"]


def process_and_ingest_lore(spark: SparkSession, raw_documents: List[str]):
    """
    Ingests raw Solo Leveling lore documents, chunks them, creates a DataFrame 
    with the strict schema, and writes it to the Unity Catalog Delta Table.
    """
    data_rows = []
    
    for source_filename, doc in raw_documents:
        # Generate chunks for each document
        for chunk in chunk_text(doc, min_size=500, max_size=800, overlap=120):
            # 1. Generate unique UUID
            row_id = str(uuid.uuid4())
            
            # 2. Extract metadata
            episode_index = mock_extract_episode_index(chunk, source_filename)
            character_tags = extract_character_tags(chunk)
            
            # 3. Append to our dataset
            data_rows.append((row_id, chunk, episode_index, character_tags))
            
    # Define the strict schema as requested
    schema = StructType([
        StructField("id", StringType(), False),
        StructField("text", StringType(), False),
        StructField("episode_index", IntegerType(), False),
        StructField("character_tags", ArrayType(StringType()), False)
    ])
    
    # Create the PySpark DataFrame
    df = spark.createDataFrame(data_rows, schema=schema)
    
    print(f"Created DataFrame with {df.count()} chunks. Preview:")
    df.show(truncate=50)
    
    # Write to Unity Catalog Delta Table using append mode
    target_table = "whispernet.rag.solo_leveling_lore"
    
    print(f"Writing data to Delta Table: {target_table} in append mode...")
    df.write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(target_table)
    print(f"Successfully wrote {df.count()} chunks to {target_table}")


if __name__ == "__main__":
    # Initialize SparkSession 
    # (Databricks natively provides 'spark', but we initialize it here for completeness)
    spark = SparkSession.builder \
        .appName("SoloLevelingLoreIngestion") \
        .getOrCreate()
        
    # ── Load all story text files from the data_ingestion directory ──
    script_dir = os.path.dirname(os.path.abspath(__file__))
    story_files = sorted([f for f in os.listdir(script_dir) if f.endswith('.txt')])
    
    if not story_files:
        print(f"No .txt story files found in {script_dir}")
    else:
        # Build list of (filename, content) tuples
        raw_documents = []
        for filename in story_files:
            filepath = os.path.join(script_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            raw_documents.append((filename, content))
            print(f"Loaded: {filename} ({len(content)} chars)")
        
        # Execute the ingestion pipeline
        process_and_ingest_lore(spark, raw_documents)
