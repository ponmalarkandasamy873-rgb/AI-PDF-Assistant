import streamlit as st
import sqlite3
import hashlib
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai
import os

st.set_page_config(
    page_title="AI PDF Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Configuration ----------
DB = "users.db"

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# ---------- Modern UI styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #f7f5ff 0%, #eef3ff 100%);
}

.block-container {
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #21134b, #35216b);
}

[data-testid="stSidebar"] * {
    color: white !important;
}

.hero {
    padding: 28px;
    border-radius: 22px;
    color: white;
    background: linear-gradient(120deg, #5936c8, #7664ef, #4e8de8);
    box-shadow: 0 10px 30px rgba(83, 58, 180, 0.18);
    margin-bottom: 24px;
}

.hero h1 {
    color: white;
    font-size: 34px;
    font-weight: 800;
    margin: 0 0 8px 0;
}

.hero p {
    color: #f0edff;
    margin: 0;
    font-size: 15px;
}

.section-title {
    color: #29204d;
    font-size: 23px;
    font-weight: 750;
    margin: 18px 0 12px 0;
}

.feature-card {
    background: rgba(255,255,255,0.92);
    border: 1px solid #e7e1ff;
    border-radius: 18px;
    padding: 20px;
    min-height: 115px;
    box-shadow: 0 5px 18px rgba(50, 35, 100, 0.05);
}

.feature-card h3 {
    color: #5133bd;
    margin: 0 0 8px 0;
    font-size: 18px;
}

.feature-card p {
    color: #625d78;
    margin: 0;
    font-size: 14px;
}

.stButton > button {
    background: linear-gradient(110deg, #6039cf, #7960ee);
    color: white;
    border: 0;
    border-radius: 11px;
    min-height: 44px;
    font-weight: 650;
    transition: 0.2s ease;
}

.stButton > button:hover {
    background: linear-gradient(110deg, #4b29b0, #6248d8);
    color: white;
    border: 0;
}

.stTextInput input, .stTextArea textarea {
    border-radius: 10px;
    border: 1px solid #ded7fa;
    background: white;
}

[data-testid="stFileUploader"] {
    background: white;
    border: 1px dashed #9b87ef;
    border-radius: 16px;
    padding: 14px;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 10px;
}

.stTabs [data-baseweb="tab"] {
    background: #ece7ff;
    border-radius: 10px 10px 0 0;
    padding: 12px 22px;
}

.stTabs [aria-selected="true"] {
    background: #ffffff;
}

div[data-testid="stExpander"] {
    background: white;
    border-radius: 12px;
    border: 1px solid #e7e1ff;
}

hr {
    border-color: #e5defa;
}
</style>
""", unsafe_allow_html=True)


# ---------- Database ----------
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


# ---------- Gemini AI ----------
def ask_ai(prompt):
    if client is None:
        raise RuntimeError(
            "Gemini API key missing. Check your .env file."
        )

    import time

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
    ]

    last_error = None

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "http_options": {"timeout": 120000}
                    },
                )
                return response.text or "No response received."

            except Exception as e:
                last_error = e
                error_text = str(e)

                if "503" in error_text or "UNAVAILABLE" in error_text.upper():
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    break

                raise RuntimeError(f"Gemini API error: {e}") from e

    raise RuntimeError(
        f"Gemini models are temporarily unavailable. "
        f"Please try again later. Details: {last_error}"
    )


# ---------- PDF extraction ----------
def extract_pdf(file):
    reader = PdfReader(file)
    return "\n".join(
        page.extract_text() or "" for page in reader.pages
    )


setup_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "summary" not in st.session_state:
    st.session_state.summary = ""

if "quiz" not in st.session_state:
    st.session_state.quiz = ""


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("# 📚 AI PDF")
    st.markdown("### ASSISTANT")
    st.markdown("---")
    st.markdown("**Your PDF workspace**")
    st.caption("Read, summarize, learn and ask questions.")
    st.markdown("---")

    if st.session_state.logged_in:
        st.success(f"Logged in as {st.session_state.username}")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.chat_history = []
            st.session_state.summary = ""
            st.session_state.quiz = ""
            st.rerun()
    else:
        st.info("Sign in to access your workspace.")

    st.markdown("---")
    st.caption("AI-powered PDF learning")


# ---------- Hero ----------
st.markdown("""
<div class="hero">
    <h1>📚 AI PDF Assistant</h1>
    <p>Your smart workspace to summarize documents, generate quizzes,
    and get answers from your PDFs.</p>
</div>
""", unsafe_allow_html=True)


# ---------- Login and registration ----------
if not st.session_state.logged_in:
    st.markdown(
        '<div class="section-title">Welcome to your workspace</div>',
        unsafe_allow_html=True,
    )
    st.write("Login to continue or create an account to get started.")

    login_tab, register_tab = st.tabs(["🔐 Login", "✨ Register"])

    with login_tab:
        with st.container(border=True):
            st.subheader("Welcome back")
            username = st.text_input("Username", key="login_user")
            password = st.text_input(
                "Password", type="password", key="login_pass"
            )

            if st.button("Login to workspace", use_container_width=True):
                with sqlite3.connect(DB) as conn:
                    row = conn.execute(
                        "SELECT password_hash FROM users WHERE username=?",
                        (username.strip(),),
                    ).fetchone()

                if row and row[0] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.username = username.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

    with register_tab:
        with st.container(border=True):
            st.subheader("Create your account")
            new_user = st.text_input("Choose a username", key="new_user")
            new_pass = st.text_input(
                "Choose a password",
                type="password",
                key="new_pass",
            )

            if st.button("Create account", use_container_width=True):
                if not new_user.strip() or len(new_pass) < 8:
                    st.error(
                        "Enter a username and a password with at least "
                        "8 characters."
                    )
                else:
                    try:
                        with sqlite3.connect(DB) as conn:
                            conn.execute(
                                "INSERT INTO users VALUES (?, ?)",
                                (new_user.strip(), hash_password(new_pass)),
                            )
                        st.success("Account created. Please log in.")
                    except sqlite3.IntegrityError:
                        st.error("That username already exists.")

    st.stop()


# ---------- Main workspace ----------
st.markdown(
    f"### 👋 Welcome, {st.session_state.username}!",
)
st.write("Upload a PDF to start working with your document.")

left, middle, right = st.columns(3)

with left:
    st.markdown("""
    <div class="feature-card">
        <h3>📝 PDF Summary</h3>
        <p>Turn lengthy documents into clear notes.</p>
    </div>
    """, unsafe_allow_html=True)

with middle:
    st.markdown("""
    <div class="feature-card">
        <h3>🎯 AI Quiz</h3>
        <p>Generate multiple-choice questions for revision.</p>
    </div>
    """, unsafe_allow_html=True)

with right:
    st.markdown("""
    <div class="feature-card">
        <h3>💬 Ask AI</h3>
        <p>Ask questions using your PDF content.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-title">📂 Your PDF workspace</div>',
            unsafe_allow_html=True)

uploaded_pdf = st.file_uploader(
    "Upload your PDF document",
    type=["pdf"],
    help="Choose a text-based PDF from your computer.",
)

if uploaded_pdf:
    try:
        pdf_text = extract_pdf(uploaded_pdf)

        st.success(f"PDF uploaded: {uploaded_pdf.name}")
        st.caption(f"Extracted text: {len(pdf_text)} characters")

        if not pdf_text.strip():
            st.warning(
                "No readable text found. This may be a scanned PDF."
            )
            st.info(
                "Scanned PDFs may need OCR before their content can be read."
            )
        else:
            with st.expander("📖 Preview PDF text"):
                st.write(pdf_text[:4000])

            summary_tab, quiz_tab, ask_tab = st.tabs([
                "📝 Summarize PDF",
                "🎯 Generate Quiz",
                "💬 Ask Questions",
            ])

            with summary_tab:
                st.write("Create a concise summary with headings and bullets.")

                if st.button("✨ Create Summary", use_container_width=True):
                    with st.spinner("Creating your summary..."):
                        try:
                            st.session_state.summary = ask_ai(
                                "Summarize this PDF clearly using headings "
                                "and bullet points:\n" + pdf_text[:12000]
                            )
                        except Exception as e:
                            st.error(str(e))

                if st.session_state.summary:
                    st.markdown("#### 📄 PDF Summary")
                    st.markdown(st.session_state.summary)
                    st.download_button(
                        "⬇️ Download Summary",
                        st.session_state.summary,
                        file_name="pdf_summary.txt",
                        use_container_width=True,
                    )

            with quiz_tab:
                st.write("Generate 10 multiple-choice questions for revision.")

                if st.button("🧠 Generate Quiz", use_container_width=True):
                    with st.spinner("Preparing your quiz..."):
                        try:
                            st.session_state.quiz = ask_ai(
                                "Create 10 multiple-choice quiz questions "
                                "from this text. Give four options and mark "
                                "the correct answer:\n" + pdf_text[:12000]
                            )
                        except Exception as e:
                            st.error(str(e))

                if st.session_state.quiz:
                    st.markdown("#### 🎯 AI Quiz")
                    st.markdown(st.session_state.quiz)
                    st.download_button(
                        "⬇️ Download Quiz",
                        st.session_state.quiz,
                        file_name="pdf_quiz.txt",
                        use_container_width=True,
                    )

            with ask_tab:
                question = st.text_input(
                    "What would you like to know about this PDF?",
                    key="pdf_question",
                    placeholder="Type your question here...",
                )

                if st.button("💬 Ask AI", use_container_width=True):
                    if question.strip():
                        with st.spinner("Finding an answer..."):
                            try:
                                answer = ask_ai(
                                    "Answer using only the PDF content below. "
                                    "If the answer is not present, say so.\n\n"
                                    f"PDF:\n{pdf_text[:12000]}\n\n"
                                    f"Question: {question}"
                                )
                                st.session_state.chat_history.append(
                                    (question, answer)
                                )
                            except Exception as e:
                                st.error(str(e))
                    else:
                        st.warning("Please type a question first.")

                if st.session_state.chat_history:
                    st.markdown("#### 💬 Chat History")

                    for q, a in reversed(st.session_state.chat_history):
                        with st.chat_message("user"):
                            st.write(q)
                        with st.chat_message("assistant"):
                            st.write(a)

    except Exception as e:
        st.error(f"Could not read this PDF: {e}")
else:
    st.info("👆 Upload a PDF above to unlock your AI tools.")

st.markdown("---")
st.caption("AI PDF Assistant • Built with Streamlit and Gemini")