# policysherlock/text_utils.py

from io import BytesIO
from docx import Document
import PyPDF2

def load_text_from_upload(uploaded_file):
    """
    Load text from uploaded PDF, DOCX, or TXT file.
    """
    if uploaded_file.type == "application/pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        return text
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(uploaded_file)
        text = "\n".join([p.text for p in doc.paragraphs])
        return text
    elif uploaded_file.type.startswith("text"):
        return uploaded_file.read().decode("utf-8")
    else:
        return ""

def chunk_text(text, chunk_size=1000):
    """
    Split text into chunks for lightweight RAG.
    """
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks

def keyword_rank(chunks, query):
    """
    Rank chunks based on query relevance (simple keyword match).
    """
    query_words = query.lower().split()
    ranked = []
    for chunk in chunks:
        score = sum(chunk.lower().count(w) for w in query_words)
        ranked.append((score, chunk))
    ranked.sort(reverse=True, key=lambda x: x[0])
    return [chunk for score, chunk in ranked]
