import streamlit as st
import google.generativeai as genai
import json
import random
from typing import List, Dict, Any
import time
import sqlite3
import hashlib
import os
from datetime import datetime

# Configure Gemini API - use environment variable or Streamlit secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY not found. Please set it as an environment variable or in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini model
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Database setup
def init_database():
    """Initialize the SQLite database with tables for users and learning history"""
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Learning history table
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
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == hashed

def create_user(username: str, password: str) -> bool:
    """Create a new user account"""
    try:
        conn = sqlite3.connect('ai_teacher.db')
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists

def authenticate_user(username: str, password: str) -> int:
    """Authenticate a user and return their user_id if successful, -1 if failed"""
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
    """Save or update a learning session"""
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    # Check if session already exists
    cursor.execute('''
        SELECT id FROM learning_history 
        WHERE user_id = ? AND topic = ? AND subtopic = ? AND learning_level = ?
    ''', (user_id, topic, subtopic, learning_level))
    
    existing = cursor.fetchone()
    
    if existing:
        # Update existing session
        cursor.execute('''
            UPDATE learning_history 
            SET progress = ?, chat_history = ?, quiz_score = ?, quiz_total = ?, last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (progress, json.dumps(chat_history), quiz_score, quiz_total, existing[0]))
    else:
        # Create new session
        cursor.execute('''
            INSERT INTO learning_history 
            (user_id, topic, subtopic, learning_level, mode, progress, chat_history, quiz_score, quiz_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, topic, subtopic, learning_level, mode, progress, json.dumps(chat_history), quiz_score, quiz_total))
    
    conn.commit()
    conn.close()

def get_user_learning_history(user_id: int) -> List[Dict]:
    """Get all learning sessions for a user"""
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT topic, subtopic, learning_level, mode, progress, quiz_score, quiz_total, 
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
            'topic': row[0],
            'subtopic': row[1],
            'learning_level': row[2],
            'mode': row[3],
            'progress': row[4],
            'quiz_score': row[5],
            'quiz_total': row[6],
            'started_at': row[7],
            'last_accessed': row[8],
            'chat_history': json.loads(row[9]) if row[9] else []
        })
    
    return history

def load_learning_session(user_id: int, topic: str, subtopic: str, learning_level: str) -> Dict:
    """Load a specific learning session"""
    conn = sqlite3.connect('ai_teacher.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT progress, chat_history, quiz_score, quiz_total, mode
        FROM learning_history 
        WHERE user_id = ? AND topic = ? AND subtopic = ? AND learning_level = ?
    ''', (user_id, topic, subtopic, learning_level))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'progress': result[0],
            'chat_history': json.loads(result[1]) if result[1] else [],
            'quiz_score': result[2],
            'quiz_total': result[3],
            'mode': result[4]
        }
    return None

# Initialize database
init_database()

# Page configuration
st.set_page_config(
    page_title="AI Expert Teacher",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 20rem !important;
        font-weight: bold !important;
        text-align: center !important;
        color: #1f77b4 !important;
        margin-bottom: 2rem !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1) !important;
    }
    .sub-header {
        font-size: 2.5rem !important;
        font-weight: bold !important;
        color: #2c3e50 !important;
        margin-bottom: 1.5rem !important;
        text-align: center !important;
    }
    .topic-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: transform 0.2s;
    }
    .topic-card:hover {
        transform: translateY(-2px);
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
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.8rem 2rem;
        font-weight: bold;
        font-size: 1.2rem;
        transition: all 0.3s;
        white-space: nowrap;
        height: 48px !important;
        min-height: 48px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
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
    
    /* Make all text bigger */
    .stMarkdown {
        font-size: 1.3rem !important;
        line-height: 1.6 !important;
    }
    
    /* Make input text bigger and align with buttons */
    .stTextInput > div > div > input {
        font-size: 1.1rem !important;
        padding: 0.75rem !important;
        height: 48px !important;
        min-height: 48px !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    
    /* Ensure input container aligns properly */
    .stTextInput > div {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    
    /* Target column containers for proper alignment */
    .stHorizontalBlock > div {
        display: flex !important;
        align-items: flex-end !important;
    }
    
    /* Ensure all columns have the same baseline alignment */
    .stHorizontalBlock > div > div {
        display: flex !important;
        align-items: flex-end !important;
        margin-bottom: 0 !important;
    }
    
    /* More aggressive targeting for button alignment */
    .stHorizontalBlock > div > div > div {
        display: flex !important;
        align-items: flex-end !important;
        margin-bottom: 0 !important;
    }
    
    /* Target the specific button containers */
    .stButton {
        display: flex !important;
        align-items: flex-end !important;
        margin-bottom: 0 !important;
        margin-top: 20px !important;
    }
    
    /* Ensure text input and buttons are on the same line */
    .stTextInput, .stButton {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    
    /* Lower the buttons specifically */
    .stButton > button {
        margin-top: 20px !important;
    }
    
    /* Make radio buttons bigger */
    .stRadio > div > div > label {
        font-size: 1.3rem !important;
        padding: 0.5rem 0 !important;
    }
    
    /* Make expander text bigger */
    .streamlit-expanderHeader {
        font-size: 1.3rem !important;
    }
    
    /* Make success/error/info messages bigger */
    .stAlert {
        font-size: 1.3rem !important;
    }
    
    /* Make sidebar text bigger */
    .css-1d391kg {
        font-size: 1.3rem !important;
    }
    
    /* Make all p tags bigger */
    p {
        font-size: 1.3rem !important;
        line-height: 1.6 !important;
    }
    
    /* Make all div text bigger */
    div {
        font-size: 1.3rem !important;
    }
    
    /* Make strong/bold text bigger */
    strong, b {
        font-size: 1.4rem !important;
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
    """Generate 5 most popular subtopics for a given topic and learning level using Gemini AI"""
    
    # Define level-specific focus areas
    level_focus = {
        "elementary": "basic concepts, foundational skills, hands-on activities, simple explanations, and fun learning",
        "middle": "building on basics, practical applications, critical thinking, real-world connections, and skill development",
        "high": "advanced concepts, detailed analysis, complex applications, theoretical understanding, and career preparation",
        "adult": "professional applications, advanced techniques, industry relevance, practical skills, and specialized knowledge"
    }
    
    focus = level_focus.get(learning_level, level_focus["middle"])
    
    # Add randomness to ensure different subtopics each time
    import random
    random_elements = [
        "unique perspectives", "different approaches", "various aspects", 
        "diverse angles", "multiple viewpoints", "alternative methods",
        "fresh insights", "new dimensions", "creative approaches"
    ]
    
    random_element = random.choice(random_elements)
    
    prompt = f"""
    You are an expert curriculum designer. For the topic "{topic}" at the {learning_level} level, generate exactly 5 BROAD, GENERAL subtopics that students at this level should learn about.
    
    Focus on: {focus}
    
    IMPORTANT: Generate {random_element} and BROAD categories, not specific techniques or detailed concepts. Think of major areas within the topic.
    
    These should be:
    - BROAD categories within the main topic (e.g., "Basic Concepts", "Advanced Techniques", "Real-World Applications")
    - Age and skill level appropriate
    - Something that can be taught in 10-15 minutes
    - General enough to cover multiple specific concepts
    - Different from typical suggestions - be creative and varied
    
    Examples of BROAD subtopics:
    - For "Math": "Basic Operations", "Problem Solving", "Real-World Applications", "Advanced Concepts", "Practical Skills"
    - For "Science": "Basic Principles", "Experiments and Methods", "Real-World Applications", "Advanced Theories", "Practical Skills"
    - For "History": "Key Events", "Important People", "Major Changes", "Cultural Impact", "Modern Connections"
    - For "Art": "Basic Techniques", "Creative Expression", "Art History", "Modern Applications", "Practical Skills"
    
    Return only a JSON array of exactly 5 strings, no additional text.
    
    Example format:
    ["Broad Category 1", "Broad Category 2", "Broad Category 3", "Broad Category 4", "Broad Category 5"]
    """
    
    try:
        response = model.generate_content(prompt)
        # Extract JSON from response
        content = response.text.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        
        subtopics = json.loads(content)
        return subtopics[:5]  # Ensure only 5 subtopics
    except Exception as e:
        st.error(f"Error generating subtopics: {e}")
        # Fallback subtopics based on level with randomness
        fallback_subtopics = {
            "elementary": ["Basic Concepts", "Simple Examples", "Fun Activities", "Easy Practice", "Real World Uses"],
            "middle": ["Building Skills", "Practical Applications", "Problem Solving", "Critical Thinking", "Hands-on Projects"],
            "high": ["Advanced Concepts", "Detailed Analysis", "Complex Applications", "Theoretical Understanding", "Career Preparation"],
            "adult": ["Professional Skills", "Advanced Techniques", "Industry Applications", "Specialized Knowledge", "Practical Implementation"]
        }
        base_subtopics = fallback_subtopics.get(learning_level, fallback_subtopics["middle"])
        # Shuffle the subtopics to add variety
        random.shuffle(base_subtopics)
        return base_subtopics

def validate_custom_subtopic(custom_subtopic: str, main_topic: str) -> bool:
    """Check if the custom subtopic is related to the main topic"""
    prompt = f"""
    Determine if the subtopic "{custom_subtopic}" is directly related to the main topic "{main_topic}".
    
    A subtopic is related if:
    - It's a specific aspect, technique, or concept within the main topic
    - It's commonly taught as part of learning the main topic
    - It's a specialized area within the main topic's domain
    
    Examples of related subtopics:
    - Main topic: "Photography", Subtopic: "Aperture settings" → RELATED
    - Main topic: "Cooking", Subtopic: "Knife skills" → RELATED
    - Main topic: "Photography", Subtopic: "Baking bread" → NOT RELATED
    - Main topic: "Cooking", Subtopic: "Car mechanics" → NOT RELATED
    
    Respond with only "RELATED" or "NOT RELATED".
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        return "RELATED" in result
    except Exception as e:
        # Default to related if there's an error
        return True

def generate_learning_content(subtopic: str, topic: str, learning_level: str) -> str:
    """Generate engaging learning content for a subtopic with structured lesson plan"""
    
    # Define level-specific teaching styles
    level_styles = {
        "elementary": {
            "tone": "warm, encouraging, and very patient like a caring elementary teacher",
            "language": "simple, clear, and uses lots of examples and analogies",
            "approach": "very hands-on with concrete examples and step-by-step guidance"
        },
        "middle": {
            "tone": "enthusiastic and supportive like a middle school teacher who believes in you",
            "language": "clear but more sophisticated, uses relatable examples",
            "approach": "encourages critical thinking while providing structure"
        },
        "high": {
            "tone": "professional yet approachable like a knowledgeable high school teacher",
            "language": "more sophisticated vocabulary, detailed explanations",
            "approach": "encourages independent thinking and deeper analysis"
        },
        "adult": {
            "tone": "professional and collaborative like a subject matter expert",
            "language": "sophisticated vocabulary, assumes prior knowledge",
            "approach": "focuses on practical applications and advanced concepts"
        }
    }
    
    style = level_styles.get(learning_level, level_styles["middle"])
    
    prompt = f"""
    You are an expert teacher specializing in {topic}, teaching a {learning_level} student about "{subtopic}". 
    
    TEACHING STYLE: {style['tone']}
    LANGUAGE: {style['language']}
    APPROACH: {style['approach']}
    
    Create an engaging initial lesson that clearly explains what "{subtopic}" is and starts teaching it. Assume the student has NO prior knowledge.
    
    Your response should be:
    - 3-4 sentences long (longer than before)
    - Start with "🎓 Welcome to [subtopic]!"
    - Clearly explain what the subtopic is and why it's important
    - Provide a brief overview of what they'll learn
    - End with an engaging question that starts the learning journey
    - Use {style['tone']} and {style['language']}
    - Make it exciting and inviting
    
    CRITICAL: Do NOT ask yes/no questions. Ask open-ended questions that encourage thinking and discussion.
    
    EXAMPLE FORMAT:
    "🎓 Welcome to [subtopic]! [Clear explanation of what this subtopic is and why it matters]. [Brief overview of what they'll learn]. [Open-ended question to start the learning journey]!"
    
    Make sure the explanation is clear and the question moves the lesson forward!
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"🎓 Welcome to {subtopic}! This is an important area within {topic} that will help you understand the bigger picture. Let's explore what this involves and why it matters. What do you think this subtopic might cover?"

def generate_quiz_questions(subtopic: str, topic: str) -> List[Dict[str, Any]]:
    """Generate quiz questions for a subtopic with less obvious answers"""
    prompt = f"""
    Create a 7-question multiple choice quiz about "{subtopic}" within the broader topic of "{topic}" for middle school students.
    
    Each question should:
    - Have 4 options (A, B, C, D) with only one correct answer
    - Be age-appropriate for middle school students
    - Use clear, simple language
    - Include real-world examples when possible
    - Range from basic to moderate difficulty
    - Be engaging and interesting
    
    CRITICAL: Make the incorrect answers believable and plausible. They should:
    - Sound reasonable to someone who doesn't know the topic well
    - Be common misconceptions or partial truths
    - Not be obviously wrong or silly
    - Be about the same length as the correct answer
    
    Return the response as a JSON array with this exact format:
    [
        {{
            "question": "Question text here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": 0,
            "explanation": "Brief, encouraging explanation of why this is correct"
        }}
    ]
    
    Only return the JSON array, no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        
        questions = json.loads(content)
        return questions
    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        # Fallback quiz
        return [
            {
                "question": f"What is the main concept of {subtopic}?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": 0,
                "explanation": "This is the correct answer because..."
            }
        ]

def assess_response_quality(user_input: str, ai_response: str, subtopic: str, learning_level: str) -> int:
    """Assess the quality of user response and return progress points (0-10)"""
    prompt = f"""
    You are an expert teacher assessing a {learning_level} student's response during a lesson about "{subtopic}".
    
    Student's response: "{user_input}"
    Teacher's previous message: "{ai_response}"
    
    Rate the student's response quality on a scale of 0-10:
    
    0-2: No response, off-topic, or completely incorrect
    3-4: Minimal effort, vague response, or misunderstanding
    5-6: Basic understanding shown, simple response
    7-8: Good understanding, thoughtful response, shows engagement
    9-10: Excellent understanding, detailed response, shows deep thinking
    
    Consider:
    - Relevance to the topic
    - Depth of understanding shown
    - Engagement and effort
    - Age-appropriate expectations for {learning_level} level
    - Whether they're building on previous learning
    
    SPECIAL RULE: If the student says "I don't know" or similar, give them 3-4 points for honesty and engagement, not 0.
    
    Return only a number from 0-10, no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        score = int(response.text.strip())
        return max(0, min(10, score))  # Ensure score is between 0-10
    except Exception as e:
        # Default to moderate score if assessment fails
        return 5

def determine_teaching_adaptation(user_input: str, current_progress: int, learning_level: str) -> str:
    """Determine how to adapt teaching based on user response and current progress"""
    prompt = f"""
    You are an expert teacher adapting your lesson for a {learning_level} student.
    
    Student's latest response: "{user_input}"
    Current learning progress: {current_progress}%
    
    Based on this response and progress, determine the teaching adaptation needed to move toward 100% knowledge:
    
    If progress is 0-20% and response shows confusion or "I don't know":
    - "REVIEW_BASICS" - Go back to fundamental concepts, use simpler language
    
    If progress is 0-20% and response shows basic understanding:
    - "BUILD_FOUNDATION" - Continue with foundational concepts, add more examples
    
    If progress is 21-50% and response shows good understanding:
    - "ADVANCE_SLOWLY" - Introduce more complex concepts gradually
    
    If progress is 21-50% and response shows confusion or "I don't know":
    - "CLARIFY_CONCEPTS" - Re-explain current concepts with different examples
    
    If progress is 51-80% and response shows strong understanding:
    - "CHALLENGE_DEEPER" - Introduce advanced concepts and critical thinking
    
    If progress is 51-80% and response shows gaps or "I don't know":
    - "REINFORCE_CORE" - Strengthen understanding of core concepts
    
    If progress is 81-100% and response shows mastery:
    - "APPLY_KNOWLEDGE" - Focus on real-world applications and synthesis
    
    If progress is 81-100% and response shows gaps or "I don't know":
    - "FILL_GAPS" - Address specific areas of misunderstanding
    
    Return only the adaptation strategy (e.g., "REVIEW_BASICS", "ADVANCE_SLOWLY"), no additional text.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Default adaptation based on progress
        if current_progress < 30:
            return "BUILD_FOUNDATION"
        elif current_progress < 70:
            return "ADVANCE_SLOWLY"
        else:
            return "CHALLENGE_DEEPER"

def handle_chat_response(user_input: str, subtopic: str, topic: str, chat_history: List[Dict], learning_level: str, current_progress: int) -> str:
    """Handle user chat input and generate AI response with adaptive teaching"""
    
    # Build conversation context
    conversation_context = ""
    if chat_history:
        # Include last few exchanges for context
        recent_history = chat_history[-6:]  # Last 3 exchanges (6 messages)
        for msg in recent_history:
            role = "Student" if msg["role"] == "user" else "Teacher"
            conversation_context += f"{role}: {msg['content']}\n"
    
    # Determine teaching adaptation
    adaptation = determine_teaching_adaptation(user_input, current_progress, learning_level)
    
    # Define level-specific teaching styles
    level_styles = {
        "elementary": {
            "tone": "warm, encouraging, and very patient like a caring elementary teacher",
            "language": "simple, clear, and uses lots of examples and analogies",
            "approach": "very hands-on with concrete examples and step-by-step guidance"
        },
        "middle": {
            "tone": "enthusiastic and supportive like a middle school teacher who believes in you",
            "language": "clear but more sophisticated, uses relatable examples",
            "approach": "encourages critical thinking while providing structure"
        },
        "high": {
            "tone": "professional yet approachable like a knowledgeable high school teacher",
            "language": "more sophisticated vocabulary, detailed explanations",
            "approach": "encourages independent thinking and deeper analysis"
        },
        "adult": {
            "tone": "professional and collaborative like a subject matter expert",
            "language": "sophisticated vocabulary, assumes prior knowledge",
            "approach": "focuses on practical applications and advanced concepts"
        }
    }
    
    style = level_styles.get(learning_level, level_styles["middle"])
    
    # Define adaptation strategies focused on progress toward 100%
    adaptation_strategies = {
        "REVIEW_BASICS": "Go back to the very basics. Use extremely simple language, lots of analogies, and concrete examples. Build confidence step by step toward understanding.",
        "BUILD_FOUNDATION": "Continue building the foundation. Use clear explanations with multiple examples. Ensure solid understanding before moving forward toward mastery.",
        "ADVANCE_SLOWLY": "Introduce slightly more complex concepts gradually. Build on what they know while adding new layers of understanding to reach deeper knowledge.",
        "CLARIFY_CONCEPTS": "Re-explain current concepts using different examples and approaches. Address any confusion directly to keep progress moving forward.",
        "CHALLENGE_DEEPER": "Introduce more advanced concepts and encourage critical thinking. Push them to think more deeply about the topic to reach expert level.",
        "REINFORCE_CORE": "Strengthen understanding of core concepts. Use different examples and applications to solidify knowledge for mastery.",
        "APPLY_KNOWLEDGE": "Focus on real-world applications and synthesis. Help them connect concepts and think creatively to achieve full understanding.",
        "FILL_GAPS": "Address specific areas of misunderstanding. Provide targeted explanations for any gaps in knowledge to reach 100% comprehension."
    }
    
    adaptation_instruction = adaptation_strategies.get(adaptation, "Continue building understanding with appropriate challenge level toward mastery.")
    
    prompt = f"""
    You are an expert teacher helping a {learning_level} student learn about "{subtopic}" within the broader topic of "{topic}".
    
    TEACHING STYLE: {style['tone']}
    LANGUAGE: {style['language']}
    APPROACH: {style['approach']}
    
    CURRENT PROGRESS: {current_progress}%
    GOAL: Get student from 0% to 100% knowledge of "{subtopic}"
    ADAPTATION STRATEGY: {adaptation}
    ADAPTATION INSTRUCTION: {adaptation_instruction}
    
    Previous conversation context:
    {conversation_context}
    
    The student just said: "{user_input}"
    
    Your response should:
    - Use {style['tone']} and {style['language']}
    - Follow the {adaptation} strategy: {adaptation_instruction}
    - Be SHORT and CONCISE (1-2 paragraphs maximum)
    - Focus on moving the lesson FORWARD toward 100% knowledge
    - Ask EXACTLY ONE question that progresses the learning journey
    - Connect to real-world relevance
    - TAKE INITIATIVE: Guide the process step by step
    - End with ONLY ONE engaging question that moves them closer to mastery
    - Adapt the difficulty level based on their current progress ({current_progress}%)
    
    CRITICAL RULES:
    1. Ask EXACTLY ONE question - no more, no less
    2. Do NOT ask yes/no questions - ask open-ended questions that encourage thinking
    3. Every response should help move from current progress ({current_progress}%) toward 100% knowledge
    4. Each question and explanation should be a step forward in the learning journey
    5. If they say "I don't know", be encouraging and provide a simpler explanation
    
    If progress is low (0-30%): Use simpler language, more examples, build confidence
    If progress is medium (31-70%): Balance explanation with challenge, encourage deeper thinking
    If progress is high (71-100%): Focus on applications, synthesis, and advanced concepts
    
    Remember: You're actively guiding their learning journey from no knowledge to complete mastery!
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "That's a great question! Let's explore this together and move forward in our learning journey..."

def show_login_page():
    """Display login page"""
    st.markdown('<h1 class="main-header">🎓 Profexa AI</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="sub-header">🔐 Welcome Back!</h2>', unsafe_allow_html=True)
    
    with st.container():
        # Login form
        with st.form("login_form"):
            username = st.text_input("Username:", placeholder="Enter your username")
            password = st.text_input("Password:", type="password", placeholder="Enter your password")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                submit_button = st.form_submit_button("🔐 Login", use_container_width=True)
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
        st.markdown('<h2 class="sub-header">Create Your Account</h2>', unsafe_allow_html=True)
        
        with st.form("signup_form"):
            username = st.text_input("Username", placeholder="Choose a username")
            password = st.text_input("Password", type="password", placeholder="Choose a password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
            submit_button = st.form_submit_button("📝 Create Account", use_container_width=True)
            
            if submit_button:
                if username and password and confirm_password:
                    if password == confirm_password:
                        if len(password) >= 6:
                            if create_user(username, password):
                                st.success("✅ Account created successfully! Please log in.")
                                st.session_state.show_signup = False
                                st.rerun()
                            else:
                                st.error("❌ Username already exists")
                        else:
                            st.warning("⚠️ Password must be at least 6 characters long")
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
        # Home button for guests
        if st.sidebar.button("🏠 Home", use_container_width=True):
            # Clear session state for new session
            for key in ['current_topic', 'current_subtopic', 'mode', 'chat_history', 
                       'quiz_questions', 'current_question', 'quiz_score', 'quiz_answers',
                       'subtopics', 'learning_progress', 'lesson_start_time']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.info("👤 Guest Mode - No history saved")
        return
    
    if 'user_id' in st.session_state:
        history = get_user_learning_history(st.session_state.user_id)
        
        # Home button
        if st.sidebar.button("🏠 Home", use_container_width=True):
            # Clear session state for new session
            for key in ['current_topic', 'current_subtopic', 'mode', 'chat_history', 
                       'quiz_questions', 'current_question', 'quiz_score', 'quiz_answers',
                       'subtopics', 'learning_progress', 'lesson_start_time']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
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
            for message in st.session_state.chat_history:
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
            send_button = st.button("💬 Send", key="send_learn", use_container_width=True)
        
        with col3:
            dont_know_button = st.button("❓ I Don't Know", key="dont_know", use_container_width=True)
        
        # Progress bar at the bottom
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown(f"**Learning Progress: {st.session_state.learning_progress}%**")
        st.markdown(f'<div class="progress-bar" style="width: {st.session_state.learning_progress}%;"></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Handle button clicks and Enter key press
        if send_button or dont_know_button or (user_input and user_input.strip()):
            # Check if this is a new message (not just the initial load)
            if 'last_user_input' not in st.session_state:
                st.session_state.last_user_input = ""
            
            # Determine the actual user input
            actual_input = "I don't know" if dont_know_button else user_input.strip()
            
            if actual_input != st.session_state.last_user_input and actual_input:
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
        
        if not st.session_state.quiz_questions:
            with st.spinner("🤖 Creating your quiz..."):
                st.session_state.quiz_questions = generate_quiz_questions(
                    st.session_state.current_subtopic,
                    st.session_state.current_topic
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
                key=f"quiz_question_{st.session_state.current_question}"
            )
            
            if st.button("✅ Submit Answer", use_container_width=True):
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