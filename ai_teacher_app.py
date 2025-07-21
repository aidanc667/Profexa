import streamlit as st
import google.generativeai as genai
import json
import sqlite3
import hashlib
import os
import time
from datetime import datetime
from typing import List, Dict, Any

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

# Temporarily allow app to run without API key for testing
if not GEMINI_API_KEY:
    st.warning("⚠️ GEMINI_API_KEY not found. Some features may not work. Please set it as an environment variable or in .streamlit/secrets.toml")
    # Don't stop the app, just show a warning
    model = None
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    except Exception as e:
        st.error(f"❌ Error configuring Gemini API: {e}")
        model = None

# Database setup
def init_database():
    """Initialize the SQLite database"""
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            subtopic TEXT NOT NULL,
            learning_level TEXT NOT NULL,
            mode TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            chat_history TEXT,
            quiz_score INTEGER DEFAULT 0,
            quiz_total INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_user(username: str, password: str) -> bool:
    try:
        conn = sqlite3.connect('ai_teacher.db')
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(username: str, password: str) -> int:
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result and verify_password(password, result[1]):
        return result[0]
    return -1

def save_learning_session(user_id: int, topic: str, subtopic: str, learning_level: str, mode: str, 
                         progress: int, chat_history: List[Dict], quiz_score: int = 0, quiz_total: int = 0):
    if not user_id:  # Don't save for guest users
        return
        
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM learning_history 
        WHERE user_id = ? AND topic = ? AND subtopic = ? AND learning_level = ?
    ''', (user_id, topic, subtopic, learning_level))
    
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('''
            UPDATE learning_history 
            SET progress = ?, chat_history = ?, quiz_score = ?, quiz_total = ?, last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (progress, json.dumps(chat_history), quiz_score, quiz_total, existing[0]))
    else:
        cursor.execute('''
            INSERT INTO learning_history 
            (user_id, topic, subtopic, learning_level, mode, progress, chat_history, quiz_score, quiz_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, topic, subtopic, learning_level, mode, progress, json.dumps(chat_history), quiz_score, quiz_total))
    
    conn.commit()
    conn.close()

def get_user_learning_history(user_id: int) -> List[Dict]:
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, topic, subtopic, learning_level, mode, progress, quiz_score, quiz_total, 
               started_at, last_accessed, chat_history
        FROM learning_history 
        WHERE user_id = ? 
        ORDER BY last_accessed DESC
    ''', (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    history = []
    for row in results:
        history.append({
            'id': row[0],
            'topic': row[1],
            'subtopic': row[2],
            'learning_level': row[3],
            'mode': row[4],
            'progress': row[5],
            'quiz_score': row[6],
            'quiz_total': row[7],
            'started_at': row[8],
            'last_accessed': row[9],
            'chat_history': json.loads(row[10]) if row[10] else []
        })
    
    return history

def delete_learning_session(session_id: int) -> bool:
    """Delete a learning session from the database"""
    try:
        conn = sqlite3.connect('ai_teacher.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM learning_history WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error deleting session: {e}")
        return False

# Initialize database
init_database()

# Page configuration
st.set_page_config(
    page_title="Profexa AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Force white background on all devices */
    .main {
        background-color: white !important;
    }
    
    .stApp {
        background-color: white !important;
    }
    
    /* Override dark mode for mobile */
    @media (prefers-color-scheme: dark) {
        .main {
            background-color: white !important;
        }
        .stApp {
            background-color: white !important;
        }
    }
    
    .main-header {
        font-size: 3rem !important;
        font-weight: bold !important;
        text-align: center !important;
        color: #1f77b4 !important;
        margin-bottom: 2rem !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1) !important;
    }
    
    .sub-header {
        font-size: 2rem !important;
        font-weight: bold !important;
        color: #2c3e50 !important;
        margin-bottom: 1.5rem !important;
        text-align: center !important;
    }
    
    .chat-message {
        padding: 1rem !important;
        margin: 0.5rem 0 !important;
        border-radius: 10px !important;
        font-size: 1.1rem !important;
    }
    
    .user-message {
        background-color: #e3f2fd !important;
        border-left: 4px solid #2196f3 !important;
    }
    
    .ai-message {
        background-color: #f3e5f5 !important;
        border-left: 4px solid #9c27b0 !important;
    }
    
    .quiz-question {
        background-color: #fff3e0 !important;
        padding: 1.5rem !important;
        border-radius: 10px !important;
        margin: 1rem 0 !important;
        border-left: 4px solid #ff9800 !important;
        font-size: 1.2rem !important;
    }
    
    .progress-container {
        margin-top: 2rem !important;
        padding: 1rem !important;
        background-color: #f5f5f5 !important;
        border-radius: 10px !important;
    }
    
    .progress-bar {
        height: 20px !important;
        background: linear-gradient(90deg, #4caf50, #8bc34a) !important;
        border-radius: 10px !important;
        transition: width 0.3s ease !important;
    }
    
    .stButton > button {
        font-size: 1rem !important;
        padding: 0.75rem 1rem !important;
        height: auto !important;
        min-height: 50px !important;
        width: 100% !important;
        background: linear-gradient(135deg, #6A8EEB 0%, #8A2BE2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        font-weight: bold !important;
        transition: all 0.3s !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.2 !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }
    
    /* Mobile-specific button adjustments */
    @media (max-width: 768px) {
        .stButton > button {
            font-size: 0.9rem !important;
            padding: 0.6rem 0.8rem !important;
            min-height: 45px !important;
        }
    }
    
    .stTextInput > div > div > input {
        font-size: 1.1rem !important;
        padding: 0.75rem !important;
    }
    
    /* Fix selectbox width and arrow alignment */
    .stSelectbox, .stSelectbox > div, .stSelectbox > div > div {
        width: 100% !important;
        box-sizing: border-box !important;
    }
    .stSelectbox > div > div > div {
        font-size: 0.95rem !important;
        padding: 0.5rem !important;
        font-family: 'Inter', 'Segoe UI', 'Arial', 'sans-serif' !important;
        white-space: nowrap !important;
        text-overflow: ellipsis !important;
        overflow: hidden !important;
        /* Remove min-width, max-width, white-space, text-overflow, overflow-wrap */
    }
    
    /* Make login/signup buttons wider with gradient */
    .stForm > div > div > div > div > button {
        width: 100% !important;
        min-width: 200px !important;
        background: linear-gradient(135deg, #6A8EEB 0%, #8A2BE2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        font-weight: bold !important;
        transition: all 0.3s !important;
    }
    
    .stForm > div > div > div > div > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = None
if 'learning_level' not in st.session_state:
    st.session_state.learning_level = None
if 'subtopics' not in st.session_state:
    st.session_state.subtopics = []
if 'current_subtopic' not in st.session_state:
    st.session_state.current_subtopic = None
if 'mode' not in st.session_state:
    st.session_state.mode = None  # 'learn' or 'quiz'
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'quiz_questions' not in st.session_state:
    st.session_state.quiz_questions = []
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'quiz_score' not in st.session_state:
    st.session_state.quiz_score = 0
if 'quiz_answers' not in st.session_state:
    st.session_state.quiz_answers = []
if 'last_user_input' not in st.session_state:
    st.session_state.last_user_input = ""
if 'last_topic_input' not in st.session_state:
    st.session_state.last_topic_input = ""
if 'last_custom_input' not in st.session_state:
    st.session_state.last_custom_input = ""
if 'clear_input' not in st.session_state:
    st.session_state.clear_input = False
if 'learning_progress' not in st.session_state:
    st.session_state.learning_progress = 0
if 'lesson_start_time' not in st.session_state:
    st.session_state.lesson_start_time = None

def generate_popular_subtopics(topic: str, learning_level: str) -> List[str]:
    """Generate popular subtopics for a given topic and learning level"""
    
    level_focus = {
        "elementary": "basic concepts, foundational skills, hands-on activities",
        "middle": "building on basics, practical applications, critical thinking",
        "high": "advanced concepts, detailed analysis, complex applications",
        "adult": "professional applications, advanced techniques, industry relevance"
    }
    
    focus = level_focus.get(learning_level, level_focus["middle"])
    
    prompt = f"""
    For the topic "{topic}" at the {learning_level} level, generate exactly 5 BROAD subtopics.
    Focus on: {focus}
    
    Return only a JSON array of exactly 5 strings.
    Example: ["Basic Concepts", "Practical Applications", "Advanced Techniques", "Real-World Examples", "Problem Solving"]
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        
        subtopics = json.loads(content)
        return subtopics[:5]
    except Exception as e:
        # Fallback subtopics
        fallback = {
            "elementary": ["Basic Concepts", "Simple Examples", "Fun Activities", "Easy Practice", "Real World Uses"],
            "middle": ["Building Skills", "Practical Applications", "Problem Solving", "Critical Thinking", "Hands-on Projects"],
            "high": ["Advanced Concepts", "Detailed Analysis", "Complex Applications", "Theoretical Understanding", "Career Preparation"],
            "adult": ["Professional Skills", "Advanced Techniques", "Industry Applications", "Specialized Knowledge", "Practical Implementation"]
        }
        return fallback.get(learning_level, fallback["middle"])

def validate_custom_subtopic(custom_subtopic: str, main_topic: str) -> bool:
    """Check if the custom subtopic is related to the main topic"""
    prompt = f"""
    Is "{custom_subtopic}" related to "{main_topic}"?
    Respond with only "YES" or "NO".
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        return "YES" in result
    except:
        return True

def generate_learning_content(subtopic: str, topic: str, learning_level: str) -> str:
    """Generate engaging learning content for a subtopic"""
    
    level_styles = {
        "elementary": "warm, encouraging, and very patient like a caring elementary teacher",
        "middle": "enthusiastic and supportive like a middle school teacher",
        "high": "professional yet approachable like a knowledgeable high school teacher",
        "adult": "professional and collaborative like a subject matter expert"
    }
    
    style = level_styles.get(learning_level, level_styles["middle"])
    
    prompt = f"""
    You are an expert teacher teaching "{subtopic}" within the broader topic of "{topic}" to {learning_level} level students.
    
    Teaching style: {style}
    
    Create a concise, engaging introduction to this subtopic that:
    1. Explains what this subtopic is about
    2. Connects it to what students might already know
    3. Sets up the learning journey
    4. Ends with an engaging question to start the conversation
    
    Keep it under 150 words and make it conversational and warm.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Welcome to learning about {subtopic}! This is an important part of {topic} that we'll explore together. What would you like to know about {subtopic}?"

def generate_quiz_questions(subtopic: str, topic: str, learning_level: str) -> List[Dict[str, Any]]:
    """Generate 7 quiz questions for a subtopic based on learning level"""
    
    # Adjust difficulty based on learning level
    level_descriptions = {
        "elementary": "very basic, simple concepts suitable for young children",
        "middle": "intermediate concepts with some complexity",
        "high": "advanced concepts with detailed explanations",
        "adult": "comprehensive, in-depth questions for adult learners"
    }
    
    difficulty = level_descriptions.get(learning_level, "intermediate")
    
    prompt = f"""
    Create 7 multiple-choice quiz questions about "{subtopic}" within the topic "{topic}".
    
    Difficulty level: {difficulty}
    
    Each question should have:
    - A clear question appropriate for {learning_level} level
    - 4 answer options (A, B, C, D)
    - One correct answer
    - A brief explanation of why the answer is correct
    
    Return as JSON array with format:
    [
        {{
            "question": "Question text?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": 0,
            "explanation": "Explanation of why this is correct"
        }}
    ]
    
    Make exactly 7 questions that progressively increase in difficulty within the {learning_level} level.
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        
        questions = json.loads(content)
        return questions[:7]
    except Exception as e:
        # Fallback questions
        return [
            {
                "question": f"What is the main concept of {subtopic}?",
                "options": ["Basic understanding", "Advanced technique", "Historical context", "Future application"],
                "correct_answer": 0,
                "explanation": "This covers the fundamental concept."
            }
        ]

def assess_response_quality(user_input: str, ai_response: str, subtopic: str, learning_level: str) -> int:
    """Assess the quality of user's response and return progress points"""
    
    prompt = f"""
    Assess this student response about "{subtopic}" at {learning_level} level:
    
    Student: "{user_input}"
    Teacher's explanation: "{ai_response}"
    
    Rate understanding from 0-10:
    0-2: No understanding
    3-4: Basic awareness
    5-6: Some understanding
    7-8: Good understanding
    9-10: Excellent understanding
    
    Return only the number (0-10).
    """
    
    try:
        response = model.generate_content(prompt)
        score = int(response.text.strip())
        return max(0, min(10, score))
    except:
        return 5  # Default middle score

def determine_teaching_adaptation(user_input: str, current_progress: int, learning_level: str) -> str:
    """Determine how to adapt teaching based on user response and progress"""
    
    if current_progress < 30:
        return "foundational"
    elif current_progress < 70:
        return "intermediate"
    else:
        return "advanced"

def handle_chat_response(user_input: str, subtopic: str, topic: str, chat_history: List[Dict], learning_level: str, current_progress: int) -> str:
    """Generate AI response for chat interaction"""
    
    adaptation = determine_teaching_adaptation(user_input, current_progress, learning_level)
    
    # Build context from chat history
    context = ""
    if len(chat_history) > 0:
        recent_messages = chat_history[-3:]  # Last 3 messages
        context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
    
    prompt = f"""
    You are an expert teacher helping a {learning_level} level student learn about "{subtopic}" within "{topic}".
    
    Current progress: {current_progress}%
    Teaching adaptation: {adaptation}
    
    Recent conversation:
    {context}
    
    Student's latest response: "{user_input}"
    
    Respond as a warm, encouraging teacher who:
    1. Acknowledges the student's input
    2. Provides helpful guidance or explanation
    3. Asks exactly one engaging question to continue learning
    4. Adapts to the student's current understanding level
    5. Keeps the conversation flowing naturally
    
    Keep your response under 200 words and make it conversational.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Thank you for sharing that about {subtopic}! That's a great point. What aspect of {subtopic} would you like to explore next?"

def show_login_page():
    """Display login page"""
    st.markdown('<h1 class="main-header">🎓 Profexa AI</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="sub-header">🔐 Welcome Back!</h2>', unsafe_allow_html=True)
    
    with st.container():
        # Login form
        with st.form("login_form"):
            username = st.text_input("Username:", placeholder="Enter your username")
            password = st.text_input("Password:", type="password", placeholder="Enter your password")
            
            # Make buttons wider and better positioned
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submit_button = st.form_submit_button("🔐 Login", use_container_width=True)
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                signup_button = st.form_submit_button("📝 Sign Up", use_container_width=True)
            
            if submit_button:
                if username and password:
                    user_id = authenticate_user(username, password)
                    if user_id:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_id
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
                else:
                    st.warning("⚠️ Please fill in all fields")
            
            if signup_button:
                st.session_state.show_signup = True
                st.rerun()
        
        # Continue as Guest button (outside the form)
        st.markdown("---")
        st.markdown("### Or continue without an account:")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("👤 Continue as Guest", use_container_width=True):
                st.session_state.authenticated = True
                st.session_state.user_id = None
                st.session_state.username = "Guest"
                st.session_state.is_guest = True
                st.rerun()

def show_signup_page():
    """Display signup page"""
    st.markdown('<h1 class="main-header">🎓 Profexa AI</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="sub-header">📝 Create Account</h2>', unsafe_allow_html=True)
    
    # Create two columns for signup form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("signup_form"):
            username = st.text_input("Username", placeholder="Choose a username")
            password = st.text_input("Password", type="password", placeholder="Create a password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
            
            # Make the signup button wider
            submit_button = st.form_submit_button("📝 Create Account", use_container_width=True)
            
            if submit_button:
                if username and password and confirm_password:
                    if password == confirm_password:
                        if create_user(username, password):
                            st.success("✅ Account created successfully! You can now login.")
                            st.session_state.show_signup = False
                            st.rerun()
                        else:
                            st.error("❌ Username already exists")
                    else:
                        st.error("❌ Passwords do not match")
                else:
                    st.warning("⚠️ Please fill in all fields")
        
        st.markdown("---")
        st.markdown("Already have an account?")
        if st.button("🔐 Back to Login", use_container_width=True):
            st.session_state.show_signup = False
            st.rerun()

def format_learning_level(level: str) -> str:
    """Format learning level for display"""
    level_map = {
        "elementary": "Elementary School",
        "middle": "Middle School",
        "high": "High School",
        "adult": "Adult"
    }
    return level_map.get(level, level.title())

def show_learning_history():
    """Display learning history in the sidebar"""
    # Don't show history for guest users
    if 'is_guest' in st.session_state and st.session_state.is_guest:
        st.sidebar.markdown("---")
        st.sidebar.info("👤 Guest Mode - No history saved")
        return
    
    if 'user_id' in st.session_state:
        history = get_user_learning_history(st.session_state.user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("## 📚 Learning History")
        
        if not history:
            st.sidebar.info("No learning sessions yet. Start your first lesson!")
            return
        
        # Separate learn and quiz history
        learn_history = [h for h in history if h['mode'] == 'learn']
        quiz_history = [h for h in history if h['mode'] == 'quiz']
        
        # Learning sessions
        if learn_history:
            st.sidebar.markdown("### 🎓 Learning Sessions")
            for i, session in enumerate(learn_history):
                with st.sidebar.expander(f"📖 {session['topic']} - {session['subtopic']}", expanded=False):
                    st.write(f"**Level:** {format_learning_level(session['learning_level'])}")
                    st.write(f"**Progress:** {session['progress']}%")
                    st.write(f"**Last accessed:** {session['last_accessed'][:10]}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # Resume button
                        if st.button(f"🔄 Resume", key=f"resume_learn_{i}", use_container_width=True):
                            st.session_state.current_topic = session['topic']
                            st.session_state.current_subtopic = session['subtopic']
                            st.session_state.learning_level = session['learning_level']
                            st.session_state.mode = session['mode']
                            st.session_state.learning_progress = session['progress']
                            st.session_state.chat_history = session['chat_history']
                            st.session_state.quiz_score = session['quiz_score']
                            st.session_state.quiz_answers = []
                            st.session_state.current_question = 0
                            st.rerun()
                    
                    with col2:
                        # Delete button
                        if st.button(f"🗑️ Delete", key=f"delete_learn_{i}", use_container_width=True):
                            if delete_learning_session(session['id']):
                                st.success("Session deleted!")
                                st.rerun()
        
        # Quiz history
        if quiz_history:
            st.sidebar.markdown("### 🧠 Quiz History")
            for i, session in enumerate(quiz_history):
                with st.sidebar.expander(f"📝 {session['topic']} - {session['subtopic']}", expanded=False):
                    st.write(f"**Level:** {format_learning_level(session['learning_level'])}")
                    if session['quiz_total'] > 0:
                        quiz_percentage = (session['quiz_score'] / session['quiz_total']) * 100
                        st.write(f"**Score:** {session['quiz_score']}/{session['quiz_total']} ({quiz_percentage:.1f}%)")
                    st.write(f"**Taken:** {session['last_accessed'][:10]}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # Retake quiz button
                        if st.button(f"🔄 Retake Quiz", key=f"retake_quiz_{i}", use_container_width=True):
                            st.session_state.current_topic = session['topic']
                            st.session_state.current_subtopic = session['subtopic']
                            st.session_state.learning_level = session['learning_level']
                            st.session_state.mode = "quiz"
                            st.session_state.quiz_score = 0
                            st.session_state.quiz_answers = []
                            st.session_state.current_question = 0
                            st.rerun()
                    
                    with col2:
                        # Delete button
                        if st.button(f"🗑️ Delete", key=f"delete_quiz_{i}", use_container_width=True):
                            if delete_learning_session(session['id']):
                                st.success("Session deleted!")
                                st.rerun()

def main():
    """Main application function"""
    
    # Initialize session state for authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'show_signup' not in st.session_state:
        st.session_state.show_signup = False
    
    # Show authentication pages if not logged in
    if not st.session_state.authenticated:
        if st.session_state.show_signup:
            show_signup_page()
        else:
            show_login_page()
        return
    
    # User is authenticated - show main app
    # Sidebar with user info and learning history
    if 'is_guest' in st.session_state and st.session_state.is_guest:
        st.sidebar.markdown(f"## 👤 Welcome, Guest!")
    else:
        st.sidebar.markdown(f"## 👤 Welcome, {st.session_state.username}!")
    
    # Home button
    if st.sidebar.button("🏠 Home", use_container_width=True):
        # Reset to topic selection
        st.session_state.current_topic = None
        st.session_state.current_subtopic = None
        st.session_state.mode = None
        st.session_state.chat_history = []
        st.session_state.quiz_questions = []
        st.session_state.current_question = 0
        st.session_state.quiz_score = 0
        st.session_state.quiz_answers = []
        st.session_state.learning_progress = 0
        st.session_state.subtopics = []  # Clear subtopics for new topic
        st.rerun()
    
    # Logout button
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Show learning history
    show_learning_history()
    
    # Main content area
    st.markdown('<h1 class="main-header">🎓 Profexa AI</h1>', unsafe_allow_html=True)
    
    # Initialize session state for the main app
    if 'current_topic' not in st.session_state:
        st.session_state.current_topic = None
    if 'learning_level' not in st.session_state:
        st.session_state.learning_level = None
    if 'subtopics' not in st.session_state:
        st.session_state.subtopics = []
    if 'current_subtopic' not in st.session_state:
        st.session_state.current_subtopic = None
    if 'mode' not in st.session_state:
        st.session_state.mode = None  # 'learn' or 'quiz'
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = []
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    if 'quiz_score' not in st.session_state:
        st.session_state.quiz_score = 0
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = []
    if 'last_user_input' not in st.session_state:
        st.session_state.last_user_input = ""
    if 'last_topic_input' not in st.session_state:
        st.session_state.last_topic_input = ""
    if 'last_custom_input' not in st.session_state:
        st.session_state.last_custom_input = ""
    if 'clear_input' not in st.session_state:
        st.session_state.clear_input = False
    if 'learning_progress' not in st.session_state:
        st.session_state.learning_progress = 0
    if 'lesson_start_time' not in st.session_state:
        st.session_state.lesson_start_time = None

    # Main app logic
    if not st.session_state.current_topic:
        # Topic and level selection
        st.markdown('<h2 class="sub-header">🎯 What would you like to learn today?</h2>', unsafe_allow_html=True)
        
        # Topic input
        topic_input = st.text_input(
            "Enter any topic you want to learn about:",
            placeholder="e.g., Math, Science, History, Programming, Cooking...",
            key="topic_input"
        )
        
        # Learning level selection
        learning_level = st.selectbox(
            "Choose your learning level:",
            ["elementary", "middle", "high", "adult"],
            format_func=lambda x: {
                "elementary": "Elementary School",
                "middle": "Middle School", 
                "high": "High School",
                "adult": "Adult"
            }[x],
            key="learning_level_select"
        )
        
        # Start learning button
        if st.button("🚀 Start Learning", use_container_width=True):
            if topic_input.strip():
                st.session_state.current_topic = topic_input.strip()
                st.session_state.learning_level = learning_level
                st.session_state.last_topic_input = topic_input.strip()
                st.session_state.subtopics = []  # Clear subtopics for new topic
                st.rerun()
            elif not topic_input.strip():
                st.warning("Please enter a topic to continue!")
    
    elif not st.session_state.current_subtopic:
        # Subtopic selection
        st.markdown(f'<h2 class="sub-header">🎯 Level: {st.session_state.current_topic}</h2>', unsafe_allow_html=True)
        st.markdown("Choose a popular subtopic or enter your own:")
        
        # Generate subtopics if not already generated
        if not st.session_state.subtopics:
            with st.spinner("🤖 Generating subtopics..."):
                st.session_state.subtopics = generate_popular_subtopics(
                    st.session_state.current_topic, 
                    st.session_state.learning_level
                )
        
        # Display popular subtopics
        for i, subtopic in enumerate(st.session_state.subtopics):
            if st.button(f"📚 {subtopic}", key=f"subtopic_{i}", use_container_width=True):
                st.session_state.current_subtopic = subtopic
                st.rerun()
        
        # Custom subtopic input
        custom_subtopic = st.text_input(
            "Choose your own subtopic within this topic:",
            placeholder="",
            key="custom_subtopic_input"
        )
        
        check_button = st.button("🔍 Check & Learn", key="custom_subtopic", use_container_width=True)
        
        # Handle both button click and Enter key press for custom subtopic
        if check_button or (custom_subtopic and custom_subtopic.strip()):
            if 'last_custom_input' not in st.session_state:
                st.session_state.last_custom_input = ""
            
            if custom_subtopic.strip() != st.session_state.last_custom_input and custom_subtopic.strip():
                with st.spinner("🤖 Checking if this subtopic is related..."):
                    if validate_custom_subtopic(custom_subtopic.strip(), st.session_state.current_topic):
                        st.session_state.current_subtopic = custom_subtopic.strip()
                        st.session_state.last_custom_input = custom_subtopic.strip()
                        st.rerun()
                    else:
                        st.error("This subtopic is unrelated to the chosen topic.")
            elif not custom_subtopic.strip():
                st.warning("Please enter a subtopic to continue!")
    
    elif not st.session_state.mode:
        # Mode selection (Learn or Quiz)
        st.markdown(f'<h2 class="sub-header">📚 {st.session_state.current_subtopic}</h2>', unsafe_allow_html=True)
        st.markdown("How would you like to explore this subtopic?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎓 Learn Mode", use_container_width=True):
                st.session_state.mode = "learn"
                st.session_state.lesson_start_time = time.time()
                st.rerun()
        
        with col2:
            if st.button("🧠 Quiz Mode", use_container_width=True):
                st.session_state.mode = "quiz"
                st.rerun()
    
    elif st.session_state.mode == "learn":
        # Learning mode with progress bar at bottom
        st.markdown(f'<h2 class="sub-header">🎓 Learning: {st.session_state.current_subtopic}</h2>', unsafe_allow_html=True)
        
        # Display chat history
        chat_container = st.container()
        
        with chat_container:
            if not st.session_state.chat_history:
                # Initial learning content
                with st.spinner("🤖 Preparing your lesson..."):
                    initial_content = generate_learning_content(
                        st.session_state.current_subtopic, 
                        st.session_state.current_topic,
                        st.session_state.learning_level
                    )
                    st.session_state.chat_history.append({
                        "role": "ai",
                        "content": initial_content
                    })
            
            # Display chat messages
            for i, message in enumerate(st.session_state.chat_history):
                if message["role"] == "user":
                    st.markdown(f'<div class="chat-message user-message">👤 You: {message["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-message ai-message">🤖 AI Teacher: {message["content"]}</div>', unsafe_allow_html=True)
        
        # User input with Enter key support and I Don't Know button
        col1, col2, col3 = st.columns([4, 1, 1])
        
        with col1:
            # Use a unique key that changes to force clearing
            input_key = f"learn_input_{len(st.session_state.chat_history)}"
            user_input = st.text_input(
                "Ask me anything about this topic or respond to my questions:",
                key=input_key,
                placeholder="Type your question or response here... (Press Enter to send)",
                value=""
            )
        
        with col2:
            send_button = st.button("💬 Send", key="send_learn", use_container_width=False)
        
        with col3:
            dont_know_button = st.button("❓ I Don't Know", key="dont_know", use_container_width=False)
        
        # Progress bar at the bottom
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown(f"**Learning Progress: {st.session_state.learning_progress}%**")
        st.markdown(f'<div class="progress-bar" style="width: {st.session_state.learning_progress}%;"></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Go to Quiz button
        if st.button("🧠 Go to Quiz", key="go_to_quiz", use_container_width=True):
            st.session_state.mode = "quiz"
            st.rerun()
        
        # Handle button clicks and Enter key press
        if send_button or dont_know_button or (user_input and user_input.strip()):
            # Check if this is a new message (not just the initial load)
            if 'last_user_input' not in st.session_state:
                st.session_state.last_user_input = ""
            
            # Determine the actual user input
            actual_input = "I don't know" if dont_know_button else user_input.strip()
            
            # Process the input if it's new and not empty
            if actual_input and actual_input != st.session_state.last_user_input:
                # Add user message to history
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": actual_input
                })
                
                # Update last input to prevent duplicate processing
                st.session_state.last_user_input = actual_input
                
                # Generate AI response with adaptive teaching
                with st.spinner("🤖 Thinking..."):
                    ai_response = handle_chat_response(
                        actual_input,
                        st.session_state.current_subtopic,
                        st.session_state.current_topic,
                        st.session_state.chat_history,
                        st.session_state.learning_level,
                        st.session_state.learning_progress
                    )
                    st.session_state.chat_history.append({
                        "role": "ai",
                        "content": ai_response
                    })
                    
                    # Assess response quality and update progress
                    if len(st.session_state.chat_history) >= 2:
                        progress_points = assess_response_quality(
                            actual_input,
                            st.session_state.chat_history[-3]["content"] if len(st.session_state.chat_history) >= 3 else "",
                            st.session_state.current_subtopic,
                            st.session_state.learning_level
                        )
                        
                        # Only increase progress if the response shows understanding (not wrong answers)
                        if progress_points >= 5:  # Only progress for good understanding
                            progress_increment = min(progress_points, 100 - st.session_state.learning_progress)
                            st.session_state.learning_progress += progress_increment
                            
                            # Ensure progress doesn't exceed 100
                            st.session_state.learning_progress = min(100, st.session_state.learning_progress)
                        # If progress_points < 5, progress stays the same (wrong answer)
                
                # Save learning session (only for authenticated users)
                if 'user_id' in st.session_state and st.session_state.user_id and not st.session_state.get('is_guest', False):
                    save_learning_session(
                        st.session_state.user_id,
                        st.session_state.current_topic,
                        st.session_state.current_subtopic,
                        st.session_state.learning_level,
                        "learn",
                        st.session_state.learning_progress,
                        st.session_state.chat_history
                    )
                
                # Clear the input and rerun
                st.session_state.last_user_input = ""
                st.rerun()
    
    elif st.session_state.mode == "quiz":
        # Quiz mode
        st.markdown(f'<h2 class="sub-header">🧠 Quiz: {st.session_state.current_subtopic}</h2>', unsafe_allow_html=True)
        st.markdown('<h3 style="text-align: center; color: #666; margin-bottom: 2rem;">(7 questions)</h3>', unsafe_allow_html=True)
        
        if not st.session_state.quiz_questions:
            with st.spinner("🤖 Creating your quiz..."):
                st.session_state.quiz_questions = generate_quiz_questions(
                    st.session_state.current_subtopic,
                    st.session_state.current_topic,
                    st.session_state.learning_level
                )
        
        if st.session_state.current_question < len(st.session_state.quiz_questions):
            question_data = st.session_state.quiz_questions[st.session_state.current_question]
            
            st.markdown(f'<div class="quiz-question">', unsafe_allow_html=True)
            st.markdown(f"**Question {st.session_state.current_question + 1}:** {question_data['question']}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Display options
            selected_answer = st.radio(
                "Choose your answer:",
                question_data["options"],
                key=f"quiz_question_{st.session_state.current_question}",
                index=None  # Don't pre-select any answer
            )
            
            # Only enable submit button if an answer is selected
            submit_disabled = selected_answer is None
            if st.button("✅ Submit Answer", use_container_width=True, disabled=submit_disabled):
                correct = question_data["options"].index(selected_answer) == question_data["correct_answer"]
                if correct:
                    st.session_state.quiz_score += 1
                    st.success("🎉 Correct!")
                else:
                    st.error("❌ Incorrect!")
                
                st.info(f"**Explanation:** {question_data['explanation']}")
                
                st.session_state.quiz_answers.append({
                    "question": question_data["question"],
                    "user_answer": selected_answer,
                    "correct_answer": question_data["options"][question_data["correct_answer"]],
                    "is_correct": correct,
                    "explanation": question_data["explanation"]
                })
                
                st.session_state.current_question += 1
                
                if st.session_state.current_question < len(st.session_state.quiz_questions):
                    st.rerun()
                else:
                    # Quiz completed
                    st.balloons()
                    st.markdown("## 🎉 Quiz Completed!")
                    
                    score_percentage = (st.session_state.quiz_score / len(st.session_state.quiz_questions)) * 100
                    st.markdown(f"**Your Score: {st.session_state.quiz_score}/{len(st.session_state.quiz_questions)} ({score_percentage:.1f}%)**")
                    
                    if score_percentage >= 80:
                        st.success("🌟 Excellent! You've mastered this subtopic!")
                    elif score_percentage >= 60:
                        st.warning("👍 Good job! You have a solid understanding.")
                    else:
                        st.info("📚 Keep learning! Review the material and try again.")
                    
                    # Save quiz session (only for authenticated users)
                    if 'user_id' in st.session_state and st.session_state.user_id and not st.session_state.get('is_guest', False):
                        save_learning_session(
                            st.session_state.user_id,
                            st.session_state.current_topic,
                            st.session_state.current_subtopic,
                            st.session_state.learning_level,
                            "quiz",
                            0,  # Quiz mode doesn't use progress percentage
                            [],  # Quiz mode doesn't use chat history
                            st.session_state.quiz_score,
                            len(st.session_state.quiz_questions)
                        )
                    
                    # Show review
                    with st.expander("📋 Review Your Answers"):
                        for i, answer in enumerate(st.session_state.quiz_answers):
                            st.markdown(f"**Q{i+1}:** {answer['question']}")
                            st.markdown(f"Your answer: {answer['user_answer']}")
                            st.markdown(f"Correct answer: {answer['correct_answer']}")
                            st.markdown(f"Explanation: {answer['explanation']}")
                            st.markdown("---")
                    
                    if st.button("🔄 Take Quiz Again", use_container_width=True):
                        st.session_state.current_question = 0
                        st.session_state.quiz_score = 0
                        st.session_state.quiz_answers = []
                        st.rerun()
                    
                    if st.button("🏠 Back to Home", use_container_width=True):
                        # Clear session state for new session
                        for key in ['current_topic', 'current_subtopic', 'mode', 'chat_history', 
                                   'quiz_questions', 'current_question', 'quiz_score', 'quiz_answers',
                                   'subtopics', 'learning_progress', 'lesson_start_time']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()

if __name__ == "__main__":
    main() 