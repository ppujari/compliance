import pdfplumber
import os
import openai
from dotenv import load_dotenv
from datetime import date
import json

# Load API key from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# 1. Extract relevant text from PDF
def extract_text_and_title(pdf_path):
    full_text = ""
    title = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text += text + "\n"
                if i == 0:
                    # Try to get the title from the first non-empty line
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    title = lines[0] if lines else ""
    return full_text, title

def extract_definitions_section(full_text):
    start = full_text.find("Definitions")
    end_keywords = ["Eligibility", "Conditions", "Applicability"]
    end = len(full_text)
    for kw in end_keywords:
        if kw in full_text[start:]:
            possible_end = full_text[start:].find(kw)
            if possible_end != -1:
                end = start + possible_end
                break
    return full_text[start:end].strip()

# 2. Use GPT to extract definitions from text
def extract_definitions_with_gpt(text):
    prompt = f"""
Extract all defined legal terms from the following section. Return a JSON list with each item containing:
- "term"
- "definition"
- "source" (e.g. Rule 2(1)(a))
- "references" (list of any terms referenced inside the definition)

Text:
{text}
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "You are a legal document parser."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response["choices"][0]["message"]["content"]

# 3. Main
if __name__ == "__main__":
    pdf_path = "data/input/1492004818999.pdf"  # Change as needed

    # Metadata
    file_name = os.path.basename(pdf_path)
    full_text, file_title = extract_text_and_title(pdf_path)
    date_extracted = date.today().isoformat()

    # Extract definitions
    definitions_text = extract_definitions_section(full_text)
    print("\n📘 Extracted Definitions Section:\n")
    print(definitions_text)

    print("\n🤖 Calling GPT to parse definitions...\n")
    definitions_json_str = extract_definitions_with_gpt(definitions_text)

    # Parse string into Python list
    try:
        definitions = json.loads(definitions_json_str)
    except json.JSONDecodeError:
        print("⚠️ Failed to parse JSON from GPT. Raw output:")
        print(definitions_json_str)
        definitions = []

    # Combine with metadata
    output = {
        "file_name": file_name,
        "file_title": file_title,
        "date_extracted": date_extracted,
        "definitions": definitions
    }
    print("\n📦 Combined Output:\n", output )    
    # Save to output file
    output_path = "data/output/definitions.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Definitions and metadata saved to: {output_path}")
