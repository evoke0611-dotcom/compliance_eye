import json

import numpy as np
import pandas as pd
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import OPENAI_API_KEY, OPENAI_MODEL


def generate_questions(api_key, kb_path, output_path, limit=None):
    client = OpenAI(api_key=api_key or OPENAI_API_KEY)
    with open(kb_path, "r", encoding="utf-8") as handle:
        chunks = [json.loads(line) for line in handle if line.strip()]
    if limit:
        chunks = chunks[:limit]

    system_prompt = """You are an expert ISMS auditor.
Generate strict JSON with:
- applicability_question
- critical_question
- options: object with A, B, C, D, E maturity options
"""
    results = []
    for chunk in chunks:
        clause_id = chunk.get("control_id", "")
        title = chunk.get("title", "")
        desc = chunk.get("description", "")
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Clause: {clause_id}\nTitle: {title}\nDescription: {desc}"},
                ],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content)
            results.append(
                {
                    "clause": clause_id,
                    "title": title,
                    "description": desc,
                    "applicability_question": parsed.get("applicability_question", ""),
                    "critical_question": parsed.get("critical_question", ""),
                    "options": parsed.get("options", {"A": "", "B": "", "C": "", "D": ""}),
                }
            )
        except Exception as exc:
            print(f"Error processing clause {clause_id}: {exc}")

    with open(output_path, "w", encoding="utf-8") as handle:
        for record in results:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return results


def validate_questions(generated_jsonl_path, gold_standard_xlsx_path, report_csv_path, final_jsonl_path):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    with open(generated_jsonl_path, "r", encoding="utf-8") as handle:
        generated_data = [json.loads(line) for line in handle if line.strip()]

    df_gold = pd.read_excel(gold_standard_xlsx_path, engine="openpyxl")
    df_gold.columns = df_gold.columns.str.strip()
    gold_dict = {}
    for _, row in df_gold.iterrows():
        subclause = str(row.get("Subclause", "")).strip()
        if subclause and subclause != "nan":
            gold_dict[subclause] = {
                "critical_question": str(row.get("Critical Question", "")),
                "format_ref": str(row.get("Format No", "")),
            }

    validation_records = []
    final_output = []
    for gen in generated_data:
        clause = str(gen.get("clause", "")).strip()
        gen_question = gen.get("critical_question", "")
        gold_info = gold_dict.get(clause)
        if gold_info and gold_info["critical_question"] and gold_info["critical_question"] != "nan":
            gold_q = gold_info["critical_question"]
            emb_gen = model.encode(gen_question)
            emb_gold = model.encode(gold_q)
            score = float(np.dot(emb_gen, emb_gold) / (np.linalg.norm(emb_gen) * np.linalg.norm(emb_gold)))
            status = "PASS" if score >= 0.75 else "FAIL"
            validation_records.append(
                {
                    "subclause": clause,
                    "gold_question": gold_q,
                    "generated_question": gen_question,
                    "similarity_score": score,
                    "status": status,
                }
            )
            gen["validation_score"] = score
            gen["validation_status"] = status
            fmt = gold_info.get("format_ref", "")
            gen["requires_format"] = bool(fmt and fmt != "nan")
            if gen["requires_format"]:
                gen["format_ref"] = fmt
        else:
            gen["validation_score"] = None
            gen["validation_status"] = "UNVERIFIED"
        final_output.append(gen)

    report = pd.DataFrame(validation_records)
    report.to_csv(report_csv_path, index=False)
    with open(final_jsonl_path, "w", encoding="utf-8") as handle:
        for record in final_output:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return report, final_output
