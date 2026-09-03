from google import genai
from google.genai import types
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import pandas as pd
import json

PROJECT_ID = "project-8b6d7fc7-f474-46f5-b88"
REGION = "us-central1"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

# ── Load database ───────────────────────────────────────────────
print("Loading database...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
print("Database ready!")

df = pd.read_csv("lexington_roads.csv")
print(f"Loaded {len(df)} road segments")

# ── temperature=0 config — fixes non-determinism ────────────────
gemini_config = types.GenerateContentConfig(
    temperature=0,
    max_output_tokens=8192,  # was 2048, responses are getting cut off
)

def check_lexington_segment(row):
    road_description = f"""
    Road Name: {row.get('Road_Name', 'Unknown')}
    Road Type: {row.get('Road_Type', 'Unknown')} (e.g. Local Road, Collector, Arterial)
    Area Type: {row.get('Area_Type', 'Unknown')}
    Number of lanes each direction: {row.get('Num_Lanes_Each_Dir', 'N/A')}
    Lane width: {row.get('Lane_Width', 'N/A')}

    LEFT SIDE OF ROAD (from driver perspective):
    - Left sidewalk width: {row.get('Left_Sidewalk_Width', 'N/A')}
    - Left shoulder width: {row.get('Left_Shoulder', 'N/A')}
    - Left edge line (marks LEFT edge of road, should be WHITE on undivided roads): {row.get('Left_Edge_Line', 'N/A')}

    CENTER OF ROAD:
    - Center line (separates opposing traffic, should be YELLOW on two-way roads): {row.get('Center_Line', 'N/A')}

    RIGHT SIDE OF ROAD (from driver perspective):
    - Right edge line (marks RIGHT edge of road, should be WHITE): {row.get('Right_Edge_Line', 'N/A')}
    - Right shoulder width: {row.get('Right_Shoulder', 'N/A')}
    - Right sidewalk width: {row.get('Right_Sidewalk', 'N/A')}

    Additional notes: {row.get('Notes', 'N/A')}
    """

    search_query = "pavement marking line width color requirements longitudinal lines edge line center line"
    relevant_chunks = retriever.invoke(search_query)
    rules_text = "\n\n".join([
        f"[Source: {doc.metadata.get('source_document', 'Unknown')}]\n{doc.page_content}"
        for doc in relevant_chunks
    ])

    prompt = f"""
You are a Massachusetts road compliance expert evaluating field measurements.

CRITICAL DEFINITIONS — read carefully before evaluating:
- LEFT EDGE LINE: white line marking the LEFT edge of the traveled way. On undivided two-way roads this should be WHITE per MUTCD 3B.09 (PM-072).
- CENTER LINE: yellow line(s) in the CENTER of the road separating opposing traffic. Should be YELLOW per MUTCD 3B.01 (PM-018).
- RIGHT EDGE LINE: white line marking the RIGHT edge of the traveled way. Should be WHITE per MUTCD 3B.09 (PM-072).
- Do NOT confuse edge lines with center lines. They are different markings with different color and placement requirements.

ROAD SEGMENT DATA:
{road_description}

RELEVANT REGULATIONS:
{rules_text}

EVALUATION RULES:
1. Normal lines must be 4-6 inches wide per MUTCD 3A.04 (PM-010)
2. Massachusetts state highways require EXACTLY 6 inch normal lines per MA amendment (PM-014)
3. For non-state-highway collectors and local roads, 4-6 inch range applies (PM-010)
4. A 6.5 inch line EXCEEDS the normal line maximum — flag as a measurement anomaly but note it may be machine error not a design deficiency
5. Center lines on two-way undivided roads must be YELLOW (PM-018)
6. Right edge lines must be WHITE (PM-072)
7. Left edge lines on undivided roads must also be WHITE (PM-072)
8. If color is not specified in the data, note it as missing information, do not assume noncompliance
9. If PDDG and MUTCD conflict, defer to PROWAG
10. For each marking, state: measured value, required value, rule ID, and compliance status

Respond with ONLY a JSON object:
{{
  "road_name": "name",
  "road_type": "classification",
  "area_type": "area type",
  "left_edge_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "center_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "right_edge_line_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "sidewalk_compliance": "Compliant or Noncompliant or Not Present or Insufficient Data",
  "overall_compliance": "Compliant or Noncompliant or Insufficient Data",
  "violations": [
    {{
      "rule_id": "e.g. PM-014",
      "rule_source": "e.g. MUTCD-MA 3A.04",
      "feature": "e.g. left edge line",
      "measured_value": "e.g. 5.5 inches white solid",
      "required_value": "e.g. 6 inches for state highways",
      "description": "one sentence explaining the specific violation"
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
  "data_quality_notes": "any missing or ambiguous input data that affected the evaluation",
  "source_document": "primary document cited",
  "section_citation": "section number",
  "explanation": "2-3 sentence overall summary of findings"
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=gemini_config,
    )
    try:
        text = response.text.strip()
        # Strip markdown code fences if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
    except Exception as e:
        # Try to extract partial JSON
        result = {
            "error": f"Could not parse: {e}",
            "road_name": row.get('Road_Name', 'Unknown'),
            "raw_truncated": response.text[:500]
        }
    return result

results = []
for i, row in df.iterrows():
    print(f"\nChecking {row.get('Road_Name')}...")
    result = check_lexington_segment(row)
    print(json.dumps(result, indent=2))
    results.append(result)

with open("lexington_results_v2.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nDone! {len(results)} verdicts saved to lexington_results_v2.json")