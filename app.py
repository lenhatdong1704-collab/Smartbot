import streamlit as st
import json
import os
import unicodedata
import google.generativeai as genai
from rapidfuzz import process, fuzz

# Cấu hình giao diện trang Web
st.set_page_config(page_title="Chatbot CSKH", page_icon="🤖")
st.title("🤖 Trợ Lý CSKH Thông Minh")

# Đường dẫn file
API_KEY = "AQ.Ab8RN6JkIexMDL5ax8v8RcC2uwzi-PRZ-wPDNw__FctNXL03gw"
HISTORY_FILE = "chat_history.json"
INTENTS_FILE = "intents.json"

# 1. Hàm làm sạch tiếng Việt
def clean_text(text):
    if not text: return ""
    text = text.lower().strip().replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize('NFD', text)
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn')

# 2. Khởi tạo Gemini Model (Lưu cache để tránh load lại nhiều lần)
@st.cache_resource
def load_model(system_instruction):
    genai.configure(api_key=API_KEY)
    return genai.GenerativeModel(model_name='gemini-3.5-flash-lite', system_instruction=system_instruction)

# 3. Đọc dữ liệu từ intents.json
if not os.path.exists(INTENTS_FILE):
    st.error(f"Không tìm thấy file {INTENTS_FILE}!")
    st.stop()

with open(INTENTS_FILE, "r", encoding="utf-8") as f:
    config_data = json.load(f)

phrase_to_intent = {clean_text(p): k for k, v in config_data["intents"].items() for p in v}
negation_words = config_data["negation_words"]
model = load_model(config_data["system_instruction"])

# 4. Quản lý trạng thái Bộ nhớ & Lịch sử trong Session State của Streamlit
if "messages" not in st.session_state:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                st.session_state.messages = json.load(f)
        except Exception:
            st.session_state.messages = []
    else:
        st.session_state.messages = []

if "chat" not in st.session_state:
    gemini_history = [{"role": m["role"], "parts": m["parts"]} for m in st.session_state.messages]
    st.session_state.chat = model.start_chat(history=gemini_history)

# 5. Thanh công cụ bên trái (Sidebar)
with st.sidebar:
    st.header("Tùy chọn")
    if st.button("🗑️ Xóa lịch sử chat"):
        st.session_state.messages = []
        st.session_state.chat = model.start_chat(history=[])
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        st.rerun()

# 6. Hiển thị lại các tin nhắn cũ lên màn hình web
for message in st.session_state.messages:
    role = "user" if message["role"] == "user" else "assistant"
    with st.chat_message(role):
        # Ẩn bớt thẻ [Gợi ý Intent: ...] khi hiển thị ra màn hình cho người dùng
        text_to_show = message["parts"][0]
        if "] Khách nói: " in text_to_show:
            text_to_show = text_to_show.split("] Khách nói: ")[-1]
        st.markdown(text_to_show)

# 7. Ô nhập liệu tin nhắn từ người dùng
if user_input := st.chat_input("Nhập tin nhắn của bạn..."):
    # Hiển thị câu hỏi của user lập tức
    with st.chat_message("user"):
        st.markdown(user_input)

    # Phân tích ý định bằng RapidFuzz
    user_clean = clean_text(user_input)
    has_negation = any(neg in user_clean.split() for neg in negation_words)
    match, score, _ = process.extractOne(user_clean, phrase_to_intent.keys(), scorer=fuzz.token_set_ratio)
    
    predicted_intent = "TRO_CHUYEEN_TU_DO" if (score < 65.0 or has_negation) else phrase_to_intent[match]
    prompt = f"[Gợi ý Intent: {predicted_intent}] Khách nói: {user_input}"

    # Gửi sang Gemini và hiển thị phản hồi
    with st.chat_message("assistant"):
        response = st.session_state.chat.send_message(prompt)
        st.markdown(response.text)

    # Lưu lại vào Session State và file JSON
    st.session_state.messages.append({"role": "user", "parts": [prompt]})
    st.session_state.messages.append({"role": "model", "parts": [response.text]})

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)