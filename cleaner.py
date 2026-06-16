import re 

def clean_text(text):
    print("Cleaning text...")
    
    # Remove watermarks, copyright, headers, footers
    text = re.sub(r'\(E\)', '', text)
    text = re.sub(r'INTERNATIONAL STANDARD', '', text)
    # Remove page markers
    text = re.sub(r'---\s*Page\s*\d+\s*---', '', text, flags=re.IGNORECASE)

    # Remove header
    text = re.sub(r'^\s*ISO\/IEC\s*27001:2022\(E\)\s*$', '', text, flags=re.MULTILINE)

    # Remove footer
    text = re.sub(r'©\s*ISO\/IEC\s*2022.*?reserved', '', text, flags=re.IGNORECASE)

    # Remove copyright block
    text = re.sub(r'COPYRIGHT PROTECTED DOCUMENT.*?Published in Switzerland', '', text, flags=re.DOTALL)

    # Remove SNV watermark
    text = re.sub(r'SNV\s*/\s*licensed to.*?ISO\/IEC\s*27001:2022', '', text, flags=re.DOTALL)

    # Remove ICS info
    text = re.sub(r'ICS.*?Price based on \d+ pages', '', text, flags=re.DOTALL)
    # Remove page markers
    text = re.sub(r'---\s*Page\s*\d+\s*---', '', text, flags=re.IGNORECASE)
    
    # Remove page numbers and lonely roman numerals
    text = re.sub(r'^\s*(?:[ivxlcdm]+|\d+)\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove zero-width spaces that might be present
    text = text.replace('\u200b', '')
    
    # Fix word breaks across line wraps (e.g., sys-\ntems -> systems)
    text = re.sub(r'(\w)[\xad\-]\n\s*(\w)', r'\1\2', text)
    
    # Locate where the actual content starts (1 Scope)
    match = re.search(r'\n1\s*\n?Scope\n', text, flags=re.IGNORECASE)
    if match:
        text = text[match.start():]
        
    # Remove Table of Contents dots and related lines
    text = re.sub(r'^.*\.{4,}.*$', '', text, flags=re.MULTILINE)
    
    # Normalize spaces and strip unicode artifacts
    text = re.sub(r'[\ufeff\x08]+', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    text = re.sub(r'ICS\s*\d+\.\d+\.\d+;\s*\d+\.\d+\s*Price based on \d+ pages','',text,flags=re.IGNORECASE) 
    text = re.sub(r'\.{3,}', ' ', text)

    text = re.sub(r'Bibliography[\s\S]*$','',text,flags=re.IGNORECASE)
    text = re.sub(r'ISO\/IEC\s*27001:2022\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Table\s*A\.1\s*\(continued\)\s*', '', text, flags=re.IGNORECASE)

    # Put list markers and NOTE labels on clearer boundaries.
    text = re.sub(r'(?<!\n)\s([a-z]\))\s', r'\n\1 ', text)
    text = re.sub(r'\s(NOTE(?:\s+\d+)?)\s', r'\n\1 ', text)
    
    return text.strip()