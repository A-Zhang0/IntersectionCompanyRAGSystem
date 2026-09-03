from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Map each PDF to a clean source label
DOCUMENTS = {
    "pddg_ch5.pdf": "MA-PDDG Chapter 5",
    "mutcd_ch3_2023.pdf": "MUTCD Chapter 3 (2023)",
    "prowag_technical.pdf": "PROWAG R3 Technical Requirements",
}

all_chunks = []
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

# Load PDFs
for filename, source_label in DOCUMENTS.items():
    print(f"Loading {filename}...")
    loader = PyPDFLoader(filename)
    pages = loader.load()
    print(f"  {len(pages)} pages loaded")
    chunks = splitter.split_documents(pages)
    for chunk in chunks:
        chunk.metadata["source_document"] = source_label
    print(f"  {len(chunks)} chunks created")
    all_chunks.extend(chunks)

# Load the text regulation file
print("Loading ma_road_provisions.txt...")
with open("ma_road_provisions.txt", "r") as f:
    text = f.read()
text_chunks = splitter.split_text(text)
for chunk in text_chunks:
    all_chunks.append(Document(
        page_content=chunk,
        metadata={"source_document": "MA Road Design Provisions (PM Rules)"}
    ))
print(f"  {len(text_chunks)} chunks created")

print(f"\nTotal chunks across all 4 documents: {len(all_chunks)}")

# Show a sample from each source
for source_label in list(DOCUMENTS.values()) + ["MA Road Design Provisions (PM Rules)"]:
    sample = next((c for c in all_chunks if c.metadata["source_document"] == source_label), None)
    if sample:
        print(f"\n--- Sample chunk from {source_label} ---")
        print(sample.page_content[:300])

print("\nDone!")