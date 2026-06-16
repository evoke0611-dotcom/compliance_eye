import docx

def read_docx(file_path):
    doc = docx.Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

if __name__ == "__main__":
    content = read_docx(r"C:\EvokeAI\Compliance Eye\Final master prompt.docx")
    with open(r"C:\EvokeAI\Compliance Eye\scratch\master_prompt.txt", "w", encoding="utf-8") as f:
        f.write(content)
