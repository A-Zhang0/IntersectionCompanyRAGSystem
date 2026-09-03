from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import pandas as pd
import json

PROJECT_ID = "project-8b6d7fc7-f474-46f5-b88"
REGION = "us-central1"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

# ── 1. Load + chunk all 3 regulation documents, tagged by source ──────
DOCUMENTS = {
    "pddg_ch5.pdf": "MA-PDDG Chapter 5",
    "mutcd_ch3_2023.pdf": "MUTCD Chapter 3 (2023)",
    "prowag_technical.pdf": "PROWAG R3 Technical Requirements",
}

print("Loading and chunking all regulation documents...")
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
all_chunks = []

for filename, source_label in DOCUMENTS.items():
    loader = PyPDFLoader(filename)
    pages = loader.load()
    chunks = splitter.split_documents(pages)
    for chunk in chunks:
        chunk.metadata["source_document"] = source_label
    all_chunks.extend(chunks)

print(f"Total chunks: {len(all_chunks)}")

# ── 2. Embed and store in ChromaDB ─────────────────────────────────────
print("Building searchable database (first run takes a minute)...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma.from_documents(all_chunks, embeddings, persist_directory="./chroma_db")
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
print("Database ready!")

# ── 3. Domain configs ──────────────────────────────────────────────────
DOMAIN_SEARCH_QUERIES = {
    "shoulder_width": "minimum shoulder width requirements",
    "lane_width": "minimum travel lane surface width requirements",
    "sidewalk_width": "minimum sidewalk width requirements",
    "crosswalk_presence": "crosswalk marking requirements pedestrian access route",
}

def format_road_row(row):
    return f"""
    Street: {row.get('St_Name', 'Unknown')}
    Right shoulder width: {row.get('Shldr_Rt_W', 'N/A')} ft
    Left shoulder width: {row.get('Shldr_Lt_W', 'N/A')} ft
    Surface/lane width: {row.get('Surface_Wd', 'N/A')} ft
    Number of lanes: {row.get('Num_Lanes', 'N/A')}
    Speed limit: {row.get('Speed_Lim', 'N/A')} mph
    """

def format_sidewalk_row(row):
    return f"""
    Sidewalk segment: {row.get('SEG_ID', 'Unknown')}
    Sidewalk width: {row.get('SWK_WIDTH', 'N/A')} ft
    Material: {row.get('MATERIAL', 'N/A')}
    Curb type: {row.get('curb_type', 'N/A')}
    """

def format_crosswalk_row(row):
    return f"""
    Crosswalk marking record (Cambridge GIS)
    Grade: {row.get('GRADE', 'N/A')}
    Marking length: {row.get('Shape__Length', 'N/A')}
    NOTE: This dataset confirms a crosswalk marking EXISTS at this location.
    It does NOT contain width measurements, so only presence/type-based
    compliance can be evaluated here, not dimensional compliance.
    """

# ── 4. Core compliance-checking function ───────────────────────────────
def check_segment(row, domain, row_formatter):
    description = row_formatter(row)
    search_query = DOMAIN_SEARCH_QUERIES[domain]
    relevant_chunks = retriever.invoke(search_query)

    rules_text = "\n\n".join([
        f"[Source: {doc.metadata['source_document']}]\n{doc.page_content}"
        for doc in relevant_chunks
    ])

    prompt = f"""
You are a road compliance expert evaluating a Massachusetts roadway feature.

FEATURE DATA:
{description}

RELEVANT REGULATIONS (each tagged with its source document):
{rules_text}

IMPORTANT RULES FOR YOUR EVALUATION:
- If different source documents give different numeric requirements for the
  same thing, DEFER TO PROWAG as the authoritative source for that conflict.
- Always cite which source document and section your verdict is based on.
- If the feature data does not contain enough information to evaluate
  compliance (e.g. no width data exists), say "Insufficient Data" - do not guess.
- Base your answer ONLY on the regulation text provided above.

Respond with ONLY a JSON object in this exact format, nothing else:
{{
  "identifier": "street name or segment ID",
  "domain_checked": "{domain}",
  "compliance_status": "Compliant or Noncompliant or Insufficient Data",
  "violated_provision": "describe the rule broken, or null if compliant",
  "source_document": "which document the cited rule came from",
  "section_citation": "section number if available",
  "explanation": "one to two sentence explanation, noting if PROWAG was used to resolve a conflict"
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    try:
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
    except Exception as e:
        result = {"error": f"Could not parse response: {e}", "raw": response.text}
    return result

# ── 5. Load all 3 datasets ──────────────────────────────────────────────
road_df = pd.read_csv("road_segments_filtered.csv")
sidewalk_df = pd.read_csv("boston_sidewalks_filtered.csv")
crosswalk_df = pd.read_csv("cambridge_crosswalks_filtered.csv")

print(f"\nLoaded {len(road_df)} road segments (shoulder/surface)")
print(f"Loaded {len(sidewalk_df)} sidewalk segments (Boston)")
print(f"Loaded {len(crosswalk_df)} crosswalk markings (Cambridge)")

# ── 6. Run a small test batch across all domains ────────────────────────
results = []

print("\n=== Domain: shoulder_width ===")
for i, row in road_df.head(10).iterrows():
    result = check_segment(row, "shoulder_width", format_road_row)
    print(json.dumps(result, indent=2))
    results.append(result)

print("\n=== Domain: lane_width ===")
for i, row in road_df.head(10).iterrows():
    result = check_segment(row, "lane_width", format_road_row)
    print(json.dumps(result, indent=2))
    results.append(result)

print("\n=== Domain: sidewalk_width ===")
for i, row in sidewalk_df.head(10).iterrows():
    result = check_segment(row, "sidewalk_width", format_sidewalk_row)
    print(json.dumps(result, indent=2))
    results.append(result)

print("\n=== Domain: crosswalk_presence ===")
for i, row in crosswalk_df.head(10).iterrows():
    result = check_segment(row, "crosswalk_presence", format_crosswalk_row)
    print(json.dumps(result, indent=2))
    results.append(result)

with open("compliance_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nDone! Results saved to compliance_results.json")