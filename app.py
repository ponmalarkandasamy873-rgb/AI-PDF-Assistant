import streamlit as st
import sqlite3
import hashlib
import requests
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="AI PDF Assistant", page_icon="📚")
DB = "users.db"

def setup_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
        """)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def ask_ai(prompt):
    api_key = st.secrets["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-3.5-flash-lite:generateContent"
    )
    response = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        },
        timeout=120
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def extract_pdf(file):
    reader = PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
    def extract_pdf_pages(file):
    reader = PdfReader(file)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


def chunk_pdf_pages(pages, chunk_size=1000, overlap=150):
    chunks = []

    for page in pages:
        text = page["text"]
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append({
                    "page": page["page"],
                    "text": chunk_text
                })

            if end >= len(text):
                break

            start = end - overlap

    return chunks


def retrieve_relevant_chunks(question, chunks, top_k=3):
    if not chunks or not question.strip():
        return []

    documents = [chunk["text"] for chunk in chunks]

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=10000
        )

        matrix = vectorizer.fit_transform(
            documents + [question]
        )

        scores = cosine_similarity(
            matrix[-1],
            matrix[:-1]
        ).flatten()

        ranked_indices = scores.argsort()[::-1]
        results = []

        for index in ranked_indices:
            if scores[index] <= 0:
                continue

            result = dict(chunks[index])
            result["score"] = float(scores[index])
            results.append(result)

            if len(results) >= top_k:
                break

        return results

    except ValueError:
        return []

setup_db()
st.title("📚 AI PDF Assistant")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if not st.session_state.logged_in:
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            with sqlite3.connect(DB) as conn:
                row = conn.execute(
                    "SELECT password_hash FROM users WHERE username=?",
                    (username.strip(),)
                ).fetchone()
            if row and row[0] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with register_tab:
        new_user = st.text_input("Create username", key="new_user")
        new_pass = st.text_input("Create password", type="password", key="new_pass")
        if st.button("Register"):
            if not new_user.strip() or len(new_pass) < 8:
                st.error("Enter a username and a password with at least 8 characters.")
            else:
                try:
                    with sqlite3.connect(DB) as conn:
                        conn.execute(
                            "INSERT INTO users VALUES (?, ?)",
                            (new_user.strip(), hash_password(new_pass))
                        )
                    st.success("Account created. Please log in.")
                except sqlite3.IntegrityError:
                    st.error("That username already exists.")

else:
    st.success(f"Welcome, {st.session_state.username}!")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.chat_history = []
        st.rerun()

    uploaded_pdf = st.file_uploader("Upload your PDF", type=["pdf"])

    if uploaded_pdf:
        try:
            pdf_text = extract_pdf(uploaded_pdf)
            st.success("PDF uploaded successfully!")
            st.write(f"Extracted text length: {len(pdf_text)} characters")

            if not pdf_text.strip():
                st.warning("No readable text found. This may be a scanned PDF.")

            with st.expander("Preview PDF text"):
                st.write(pdf_text[:4000])

            if st.button("Summarize PDF"):
                with st.spinner("Creating summary..."):
                    try:
                        st.session_state.summary = ask_ai(
                            "Summarize this PDF clearly using headings and bullet points:\n"
                            + pdf_text[:12000]
                        )
                    except Exception as e:
                        st.error(f"AI error: {e}")

            if "summary" in st.session_state:
                st.subheader("PDF Summary")
                st.write(st.session_state.summary)
                st.download_button(
                    "Download Summary", st.session_state.summary,
                    file_name="pdf_summary.txt"
                )

            if st.button("Generate Quiz"):
                with st.spinner("Creating quiz..."):
                    try:
                        st.session_state.quiz = ask_ai(
                            "Create 10 multiple-choice quiz questions from this text. "
                            "Give four options and mark the correct answer:\n"
                            + pdf_text[:12000]
                        )
                    except Exception as e:
                        st.error(f"AI error: {e}")

            if "quiz" in st.session_state:
                st.subheader("AI Quiz")
                st.write(st.session_state.quiz)
                st.download_button(
                    "Download Quiz", st.session_state.quiz,
                    file_name="pdf_quiz.txt"
                )

            st.subheader("Ask Questions from PDF")
            question = st.text_input("Type your question")

            if st.button("Ask AI"):
                if question.strip():
                    with st.spinner("Finding an answer..."):
                        try:
                            answer = ask_ai(
                                "Answer using only the PDF content below. "
                                "If the answer is not present, say so.\n\n"
                                f"PDF:\n{pdf_text[:12000]}\n\n"
                                f"Question: {question}"
                            )
                            st.session_state.chat_history.append((question, answer))
                        except Exception as e:
                            st.error(f"AI error: {e}")

            if st.session_state.chat_history:
                st.subheader("Chat History")
                for q, a in reversed(st.session_state.chat_history):
                    st.markdown(f"**Question:** {q}")
                    st.write(a)

        except Exception as e:
            st.error(f"Could not read this PDF: {e}")
    else:
        st.info("Upload a PDF to start.")
