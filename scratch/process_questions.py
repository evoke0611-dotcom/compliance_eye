import json
import re

def parse_questions(text):
    questions = []
    # Match Q1. ... A. ... B. ... C. ... D. ...
    # Or Q46. ... (Yes/No)
    lines = text.split('\n')
    current_q = None
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Check for new question
        match = re.match(r'Q(\d+)\.\s*(.*)', line)
        if match:
            if current_q:
                questions.append(current_q)
            q_id = int(match.group(1))
            q_text = match.group(2)
            
            # Extract options if present in same line
            options = []
            if 'A.' in q_text:
                parts = re.split(r'([A-D]\.)', q_text)
                q_text = parts[0].strip()
                for i in range(1, len(parts), 2):
                    if i+1 < len(parts):
                        options.append(parts[i+1].strip())
            
            current_q = {
                "id": q_id,
                "question": q_text,
                "options": options,
                "type": "mcq" if options else "yes_no"
            }
        elif current_q:
            # Handle multi-line options or questions
            if 'A.' in line or 'B.' in line or 'C.' in line or 'D.' in line:
                parts = re.split(r'([A-D]\.)', line)
                for i in range(1, len(parts), 2):
                    if i+1 < len(parts):
                        current_q["options"].append(parts[i+1].strip())
            elif "(Yes/No)" in line:
                current_q["type"] = "yes_no"
                current_q["question"] += " " + line
            else:
                current_q["question"] += " " + line

    if current_q:
        questions.append(current_q)
        
    return questions

if __name__ == "__main__":
    with open(r"C:\EvokeAI\Compliance Eye\scratch\iso_questions.txt", "r", encoding="utf-8") as f:
        text = f.read()
    
    questions = parse_questions(text)
    
    # Map questions to clauses (manual mapping based on general ISO 27001 structure)
    # 1-5: Context (4.x)
    # 6-8: Leadership (5.x)
    # 9-13: Planning/Risk (6.x)
    # 14-17: Asset Management (A.5.9-13)
    # 18-23: Access Control (A.5.15-18)
    # ... and so on
    
    for q in questions:
        if q["id"] <= 5: q["clause"] = "4"
        elif q["id"] <= 8: q["clause"] = "5"
        elif q["id"] <= 13: q["clause"] = "6"
        elif q["id"] <= 17: q["clause"] = "A.5"
        elif q["id"] <= 23: q["clause"] = "A.5"
        elif q["id"] <= 27: q["clause"] = "A.7"
        elif q["id"] <= 31: q["clause"] = "A.8"
        elif q["id"] <= 36: q["clause"] = "A.5"
        elif q["id"] <= 38: q["clause"] = "A.5"
        elif q["id"] <= 41: q["clause"] = "A.5"
        elif q["id"] <= 45: q["clause"] = "9/10"
        else: q["clause"] = "Annex A"

    with open(r"C:\EvokeAI\Compliance Eye\questions.json", "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
    
    print(f"Parsed {len(questions)} questions.")
