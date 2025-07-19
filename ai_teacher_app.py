import streamlit as st
import google.generativeai as genai
import json
import random
from typing import List, Dict, Any
import time

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyD1C2kWvWGkrTdsr9nQlsJguY21_APiZdA"
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini model
model = genai.GenerativeModel('gemini-2.0-flash-exp')

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
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .sub-header {
        font-size: 1.5rem;
        color: #2c3e50;
        margin-bottom: 1rem;
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
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .ai-message {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    .quiz-question {
        background-color: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #ff9800;
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = None
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

def generate_subtopics(topic: str) -> List[str]:
    """Generate specific subtopics for a given topic using Gemini AI"""
    prompt = f"""
    You are an expert curriculum designer. For the topic "{topic}", generate 5-7 specific, focused subtopics that would be essential for learning this subject at a middle school level.
    
    Each subtopic should be:
    - Specific and concrete (not vague like "Introduction" or "Basic Concepts")
    - Age-appropriate for middle school students
    - Something that can be taught in 10-15 minutes
    - A distinct learning objective
    
    Examples of good subtopics:
    - For "Photography": "Understanding Aperture and Depth of Field", "Composition Rules: Rule of Thirds", "Lighting: Natural vs Artificial"
    - For "Cooking": "Knife Skills and Safety", "Understanding Heat and Cooking Methods", "Flavor Building with Herbs and Spices"
    
    Return only a JSON array of strings, no additional text.
    
    Example format:
    ["Specific Subtopic 1", "Specific Subtopic 2", "Specific Subtopic 3", "Specific Subtopic 4", "Specific Subtopic 5"]
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
        return subtopics
    except Exception as e:
        st.error(f"Error generating subtopics: {e}")
        # Fallback subtopics
        return ["Introduction", "Basic Concepts", "Advanced Topics", "Practical Applications", "Common Mistakes"]

def generate_learning_content(subtopic: str, topic: str) -> str:
    """Generate engaging learning content for a subtopic"""
    prompt = f"""
    You are an expert teacher specializing in {topic}, teaching a middle school student about "{subtopic}". 
    
    You are enthusiastic, engaging, and take initiative in teaching. Start teaching immediately without waiting for questions.
    
    Your teaching style should be:
    - Conversational and friendly, like talking to a curious friend
    - Full of real-world examples and analogies that middle schoolers can relate to
    - Interactive with questions and challenges
    - Encouraging and supportive
    - Age-appropriate but not condescending
    
    Structure your lesson like this:
    1. Start with an exciting hook or interesting fact about the subtopic
    2. Explain the concept clearly with simple analogies
    3. Give 2-3 real-world examples that middle schoolers would understand
    4. Include a fun mini-challenge or activity they can do
    5. Ask them a question to check understanding
    6. End with encouragement and an invitation to ask more questions
    
    Make it feel like a natural conversation where you're actively teaching, not just waiting for questions.
    Keep your response engaging and around 3-4 paragraphs.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"I'm so excited to teach you about {subtopic}! This is one of my favorite parts of {topic}. Let me start by sharing something really cool about it..."

def generate_quiz_questions(subtopic: str, topic: str) -> List[Dict[str, Any]]:
    """Generate quiz questions for a subtopic"""
    prompt = f"""
    Create a 7-question multiple choice quiz about "{subtopic}" within the broader topic of "{topic}" for middle school students.
    
    Each question should:
    - Have 4 options (A, B, C, D) with only one correct answer
    - Be age-appropriate for middle school students
    - Use clear, simple language
    - Include real-world examples when possible
    - Range from basic to moderate difficulty
    - Be engaging and interesting
    
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

def handle_chat_response(user_input: str, subtopic: str, topic: str) -> str:
    """Handle user chat input and generate AI response"""
    prompt = f"""
    You are an expert teacher helping a middle school student learn about "{subtopic}" within the broader topic of "{topic}".
    
    The student just said: "{user_input}"
    
    Respond as an enthusiastic, engaging teacher who:
    - Takes initiative in teaching (don't just answer, expand and teach more)
    - Uses age-appropriate language and examples
    - Provides real-world analogies that middle schoolers can relate to
    - Gives encouraging feedback and praise
    - Asks follow-up questions to deepen understanding
    - Includes fun facts or mini-challenges when relevant
    - Corrects misconceptions gently and supportively
    - Maintains an excited, curious tone
    
    Your response should be:
    - Conversational and friendly
    - Educational but not overwhelming
    - Around 2-3 paragraphs
    - Include at least one question or challenge for the student
    - Encouraging and supportive
    
    Remember: You're not just answering questions - you're actively teaching and expanding their knowledge!
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "That's a fantastic question! I love your curiosity. Let me explain this in a way that will make it really clear for you..."

# Main app
def main():
    st.markdown('<h1 class="main-header">🎓 AI Expert Teacher</h1>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        if st.button("🏠 Start Over", use_container_width=True):
            st.session_state.current_topic = None
            st.session_state.subtopics = []
            st.session_state.current_subtopic = None
            st.session_state.mode = None
            st.session_state.chat_history = []
            st.session_state.quiz_questions = []
            st.session_state.current_question = 0
            st.session_state.quiz_score = 0
            st.session_state.quiz_answers = []
            st.rerun()
        
        if st.session_state.current_topic:
            st.markdown(f"**Current Topic:** {st.session_state.current_topic}")
        if st.session_state.current_subtopic:
            st.markdown(f"**Current Subtopic:** {st.session_state.current_subtopic}")
        if st.session_state.mode:
            st.markdown(f"**Mode:** {st.session_state.mode.title()}")
    
    # Main content area
    if not st.session_state.current_topic:
        # Topic selection
        st.markdown('<h2 class="sub-header">What would you like to learn today?</h2>', unsafe_allow_html=True)
        
        topic_input = st.text_input(
            "Enter any topic you want to learn more about:",
            placeholder="e.g., Math, Biology, Politics, History of Ancient Rome..."
        )
        
        if st.button("🎯 Start Learning!", use_container_width=True):
            if topic_input.strip():
                with st.spinner("🤖 Becoming an expert in your topic..."):
                    st.session_state.current_topic = topic_input.strip()
                    st.session_state.subtopics = generate_subtopics(topic_input.strip())
                st.rerun()
            else:
                st.warning("Please enter a topic to continue!")
    
    elif not st.session_state.current_subtopic:
        # Subtopic selection
        st.markdown(f'<h2 class="sub-header">🎯 Expert in: {st.session_state.current_topic}</h2>', unsafe_allow_html=True)
        st.markdown("Choose a subtopic to explore:")
        
        for i, subtopic in enumerate(st.session_state.subtopics):
            if st.button(f"📚 {subtopic}", key=f"subtopic_{i}", use_container_width=True):
                st.session_state.current_subtopic = subtopic
                st.rerun()
    
    elif not st.session_state.mode:
        # Mode selection (Learn or Quiz)
        st.markdown(f'<h2 class="sub-header">📚 {st.session_state.current_subtopic}</h2>', unsafe_allow_html=True)
        st.markdown("How would you like to explore this subtopic?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎓 Learn Mode", use_container_width=True):
                st.session_state.mode = "learn"
                st.rerun()
        
        with col2:
            if st.button("🧠 Quiz Mode", use_container_width=True):
                st.session_state.mode = "quiz"
                st.rerun()
    
    elif st.session_state.mode == "learn":
        # Learning mode
        st.markdown(f'<h2 class="sub-header">🎓 Learning: {st.session_state.current_subtopic}</h2>', unsafe_allow_html=True)
        
        # Display chat history
        chat_container = st.container()
        
        with chat_container:
            if not st.session_state.chat_history:
                # Initial learning content
                with st.spinner("🤖 Preparing your lesson..."):
                    initial_content = generate_learning_content(
                        st.session_state.current_subtopic, 
                        st.session_state.current_topic
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
        
        # User input
        user_input = st.text_input(
            "Ask me anything about this topic or respond to my questions:",
            key="learn_input",
            placeholder="Type your question or response here..."
        )
        
        if st.button("💬 Send", key="send_learn"):
            if user_input.strip():
                # Add user message to history
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": user_input.strip()
                })
                
                # Generate AI response
                with st.spinner("🤖 Thinking..."):
                    ai_response = handle_chat_response(
                        user_input.strip(),
                        st.session_state.current_subtopic,
                        st.session_state.current_topic
                    )
                    st.session_state.chat_history.append({
                        "role": "ai",
                        "content": ai_response
                    })
                
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

if __name__ == "__main__":
    main() 