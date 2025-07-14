import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import google.generativeai as genai
import re

st.set_page_config(page_title="Apexnuera HR Chatbot", page_icon="🤖", layout="centered")

st.title("🤖 Apexnuera HR Chatbot")

# --- Configuration & Secrets ---
# Streamlit will automatically read secrets from .streamlit/secrets.toml
# or Streamlit Cloud's secrets management.
# -----------------------------

# Initialize Google Gemini client
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    gemini_model = genai.GenerativeModel('gemini-pro')
except AttributeError:
    st.error("Gemini API key not found in Streamlit secrets. Please add it to your `.streamlit/secrets.toml` file or Streamlit Cloud secrets.")
    st.stop()

# Connect to Google Sheet (using Streamlit's cache for performance)
@st.cache_data(ttl=3600)
def load_sheet():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client_gspread = gspread.authorize(creds)
        sheet = client_gspread.open("apexnuera_data").sheet1 # Assumes your data is in the first sheet
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to load data from Google Sheet. Please check your `gcp_service_account` secrets and sheet name. Error: {e}")
        return pd.DataFrame()

df = load_sheet()

# Function to get specific data from the DataFrame based on keywords
def get_specific_data(user_input, dataframe):
    user_input_lower = user_input.lower()

    course_pattern = r"\b(course|learning|classes|subjects|training|program)\b"
    job_pattern = r"\b(job|hiring|openings|position|career|employment)\b"
    timing_pattern = r"\b(timing|time|schedule|when|hours)\b"

    if re.search(course_pattern, user_input_lower):
        courses = dataframe["Course Name"].dropna().unique()
        if courses.size > 0:
            return "course", "**📘 Available Courses:**\n- " + "\n- ".join(courses)
        else:
            return "course", "I don't have information about specific courses right now. Please check back later or ask a general question."

    if re.search(job_pattern, user_input_lower):
        jobs = dataframe["Job Opening"].dropna().unique()
        if jobs.size > 0:
            return "job", "**💼 Current Job Openings:**\n- " + "\n- ".join(jobs)
        else:
            return "job", "I don't have information about specific job openings right now. Please check back later or ask a general question."

    if re.search(timing_pattern, user_input_lower):
        timings = dataframe["Course Timing"].dropna().unique()
        if timings.size > 0:
            return "timing", "**🕒 Course Timings:**\n- " + "\n- ".join(timings)
        else:
            return "timing", "I don't have information about specific course timings right now. Please check back later or ask a general question."

    return "general", None

# --- Chat Loop ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm your Apexnuera HR Chatbot. How can I assist you today? You can ask me about **courses**, **job openings**, or **general HR queries**. 😊"}
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

user_input = st.chat_input("Ask me anything...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    intent, specific_reply = get_specific_data(user_input, df)

    if specific_reply:
        reply = specific_reply
    else:
        gemini_chat_history = []
        system_instruction = """You are Apexnuera's helpful and professional HR Chatbot. Your primary goal is to assist users with their inquiries in a friendly and informative manner.
        If a question is about specific 'courses', 'job openings', or 'timings', and you have **already stated** that you don't have specific data for them (e.g., "I don't have information about specific courses right now."), then provide a general helpful answer or suggest how the user might find that information (e.g., "You might want to check the official Apexnuera website or contact the HR department directly for the most up-to-date details.").
        For all other general HR-related questions, provide a clear and concise response based on your training data. Do not make up information.
        """

        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                content_to_add = msg["content"]
                if i == 0 and "assistant" not in [m["role"] for m in st.session_state.messages]: # Only prepend if this is the very first user message in the session
                    content_to_add = system_instruction + "\n\nUser: " + content_to_add
                gemini_chat_history.append({"role": "user", "parts": [content_to_add]})
            elif msg["role"] == "assistant":
                gemini_chat_history.append({"role": "model", "parts": [msg["content"]]})

        try:
            with st.spinner("Thinking..."):
                response = gemini_model.generate_content(
                    gemini_chat_history,
                    safety_settings={'HARASSMENT': 'block_none', 'HATE_SPEECH': 'block_none', 'SEXUALLY_EXPLICIT': 'block_none', 'DANGEROUS_CONTENT': 'block_none'},
                    generation_config={"temperature": 0.6, "max_output_tokens": 300}
                )
                reply = response.text

        except Exception as e:
            reply = f"I apologize, but I'm having trouble connecting to Google's AI at the moment. Please try again shortly. (Error: {e})"
            st.error(reply)

    st.chat_message("assistant").markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
