from google import genai
from google.genai import types
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import pandas as pd
import json
import time
import os

PROJECT_ID = "project-8b6d7fc7-f474-46f5-b88"
REGION = "us-central1"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

print("Loading database...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
print("Database ready!")

gemini_config = types.GenerateContentConfig(
    temperature=0,
    max_output_tokens=8192,
)

# ── Load the synthetic dataset ──────────────────────────────────
df = pd.read_csv("MA_Road___Pavement_Marking_Dataset_Bedford_.csv", encoding='latin-1')
print(f"Loaded {len(df)} rows")

# ── Resume logic — load existing results if any ─────────────────
RESULTS_FILE = "synthetic_results.json"
if os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, "r") as f:
        results = json.load(f)
    print(f"Resuming from row {len(results)} (already have {len(results)} results)")
else:
    results = []
    print("Starting fresh")

def check_row(row):
    def g(col): return str(row[col]) if col in row.index and pd.notna(row[col]) else "N/A"

    road_description = f"""
    ALL RAW DATA FOR THIS ROW:
    {row.to_dict()}
    """

    search_query = "pavement marking line width color requirements edge line center line shoulder sidewalk"
    relevant_chunks = retriever.invoke(search_query)
    rules_text = "\n\n".join([
        f"[Source: {doc.metadata.get('source_document', 'Unknown')}]\n{doc.page_content}"
        for doc in relevant_chunks
    ])

    prompt = f"""
You are a Massachusetts road compliance expert evaluating a synthetic road segment.

CRITICAL DEFINITIONS:
- LEFT EDGE LINE: white line marking LEFT edge of traveled way on undivided roads (MUTCD 3B.09)
- CENTER LINE: yellow line(s) separating opposing traffic (MUTCD 3B.01)
- RIGHT EDGE LINE: white line marking RIGHT edge of traveled way (MUTCD 3B.09)
- Do NOT confuse edge lines with center lines

ROAD SEGMENT DATA:
{road_description}

RELEVANT REGULATIONS:
{rules_text}

EVALUATION RULES:
1. Normal lines must be 4-6 inches wide (PM-010, MUTCD 3A.04)
2. Massachusetts state highways require EXACTLY 6 inch normal lines (PM-014)
3. NHS roads or speed limit >= 45 mph should have 6 inch lines (PM-015)
4. Wide lines on state highways must be 12 inches (PM-016)
5. Center lines on two-way undivided roads must be YELLOW (PM-018)
6. Right edge lines must be WHITE (PM-072)
7. Left edge lines on undivided roads must be WHITE (PM-072)
8. If color not specified, note as missing — do not assume noncompliance
9. 6.5 inch measurement = possible measurement anomaly, note it
10. If PDDG and MUTCD conflict, defer to PROWAG
11. Minimum sidewalk width is 5 feet excluding curb (MA-PDDG 5.3.1.1)

Respond with ONLY valid JSON, no markdown fences:
{{
  "segment_id": "road name or ID from the data",
  "road_type": "classification if available",
  "area_type": "area type if available",
  "left_edge_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "center_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "right_edge_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "sidewalk_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "shoulder_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "overall_compliance": "Compliant or Noncompliant or Insufficient Data",
  "violations": [
    {{
      "rule_id": "e.g. PM-014",
      "rule_source": "e.g. MUTCD-MA 3A.04",
      "feature": "e.g. left edge line",
      "measured_value": "e.g. 5 inches",
      "required_value": "e.g. 6 inches for state highways",
      "description": "one sentence"
    }}
  ],
  "compliant_features": [
    {{
      "feature": "e.g. center line color",
      "measured_value": "e.g. yellow",
      "required_value": "e.g. yellow",
      "rule_id": "PM-018"
    }}
  ],
  "data_quality_notes": "any missing or ambiguous input data",
  "source_document": "primary document cited",
  "section_citation": "section number",
  "explanation": "2-3 sentence overall summary"
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=gemini_config,
    )
    try:
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        return {
            "error": f"Could not parse: {e}",
            "segment_id": str(row.iloc[0]),
            "raw_truncated": response.text[:300]
        }

# ── Run — skipping already completed rows ───────────────────────
start_from = len(results)
errors = []

for i, row in df.iloc[start_from:].iterrows():
    seg_id = str(row.iloc[0])
    print(f"[{i+1}/{len(df)}] Checking {seg_id}...")

    # Retry logic for 429 rate limit errors
    for attempt in range(3):
        try:
            result = check_row(row)
            break
        except Exception as e:
            if "429" in str(e):
                wait = 30 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                result = {"error": str(e), "segment_id": seg_id}
                break
    else:
        result = {"error": "Failed after 3 retries", "segment_id": seg_id}

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        errors.append(i)
    else:
        status = result.get('overall_compliance', '?')
        violations = len(result.get('violations', []))
        print(f"  {status} — {violations} violation(s)")

    results.append(result)

    # Save after every row so a crash doesn't lose progress
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    # Rate limit delay — 3 seconds between requests
    time.sleep(3)

# ── Summary ─────────────────────────────────────────────────────
compliant = sum(1 for r in results if r.get('overall_compliance') == 'Compliant')
noncompliant = sum(1 for r in results if r.get('overall_compliance') == 'Noncompliant')
insufficient = sum(1 for r in results if r.get('overall_compliance') == 'Insufficient Data')

print(f"\n{'='*50}")
print(f"DONE — {len(results)} rows processed")
print(f"  Compliant:         {compliant}")
print(f"  Noncompliant:      {noncompliant}")
print(f"  Insufficient Data: {insufficient}")
print(f"  Parse errors:      {len(errors)}")
print(f"Results saved to synthetic_results.json")