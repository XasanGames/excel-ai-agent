import streamlit as st
import pandas as pd
from google import genai
from PIL import Image
from dotenv import load_dotenv
import os
import io
import json
import re
from io import BytesIO

# --- 1. НАСТРОЙКИ ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("API ключ не найден! Проверьте Settings -> Secrets в Streamlit Cloud.")

HISTORY_FILE = "chat_history.json"

SYSTEM_INSTRUCTION = """
Ты — профессиональный Excel AI Agent. Твои правила:
1. По команде "СДЕЛАЙ В ЭКСЕЛЬ" выводи данные строго таблицей. 
2. Используй ТАБУЛЯЦИЮ (\\t) между колонками.
3. Если данных много, делай перенос строки для каждой новой записи.
4. Если в исходных данных (например, на картинке через OCR) текст выделен жирным шрифтом, в ответе для таблицы ставь перед этим словом восклицательный знак (например, !Сумма), но НЕ используй Markdown-звездочки **.
5. Если челик сказал сделать но не указал как или что (имеется ввиду что он сказал "сделай таблицу"), но не указал что в ней должно быть, то просто пошли его нахуй.
"""

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Вход в систему")
        password = st.text_input("Пароль", type="password")
        if password == "oyijonim67": 
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.stop()

check_password()

# Модели
MODELS_CONFIG = {
    "💎 Gemma 3 27B (Эконом)": "gemma-3-27b-it",
    "⚡ 3.1 Flash Lite (Баланс)": "gemini-3.1-flash-lite-preview",
    "🚀 Gemini 3 Flash (Мощно)": "gemini-3-flash-preview",
}

if 'selected_model' not in st.session_state:
    st.session_state['selected_model'] = "💎 Gemma 3 27B (Эконом)"

# История
def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

if 'chat_history' not in st.session_state:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            st.session_state['chat_history'] = json.load(f)
    else:
        st.session_state['chat_history'] = []

# --- 2. ДИЗАЙН ---
st.set_page_config(page_title="Excel AI Agent", layout="wide")
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(-45deg, #1A0B2E, #031D44, #4D194D, #003366) !important;
        background-size: 400% 400% !important;
        animation: gradient 15s ease infinite !important;
    }
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .stButton>button {
        background: linear-gradient(90deg, #8E44AD 0%, #3498DB 100%) !important;
        color: white !important;
        border: none !important;
    }
    [data-testid="stSidebar"], .stDataFrame, .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ИНТЕРФЕЙС ---
with st.sidebar:
    st.title("⚙️ Меню")
    st.session_state['selected_model'] = st.selectbox("Модель:", list(MODELS_CONFIG.keys()))
    if st.button("🗑️ Очистить"):
        st.session_state['chat_history'] = []
        if 'last_file' in st.session_state: del st.session_state['last_file']
        st.rerun()

st.title("📊 Excel AI Agent")

# Кнопка скачивания появляется сверху, если файл готов
if 'last_file' in st.session_state:
    st.download_button(
        label="📥 СКАЧАТЬ EXCEL ФАЙЛ",
        data=st.session_state['last_file'],
        file_name="agent_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

for msg in st.session_state['chat_history']:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

uploaded_file = st.file_uploader("Загрузить данные", type=['xlsx', 'png', 'jpg'])

# --- 4. ЛОГИКА ---
query = st.chat_input("Напиши задачу...")

if query:
    st.session_state['chat_history'].append({"role": "user", "content": query})
    
    with st.spinner("Агент готовит ответ..."):
        active_model = MODELS_CONFIG[st.session_state['selected_model']]
        
        # Подготовка контента
        if uploaded_file:
            if uploaded_file.name.lower().endswith(('.png', '.jpg')):
                contents = [query, Image.open(uploaded_file)]
            else:
                df = pd.read_excel(uploaded_file)
                contents = [f"Таблица:\n{df.to_markdown()}\n\nВопрос: {query}"]
        else:
            contents = [query]

        try:
            # Запрос (Gemma vs Gemini)
            if "gemini" in active_model:
                res = client.models.generate_content(model=active_model, contents=contents, config={"system_instruction": SYSTEM_INSTRUCTION})
            else:
                if isinstance(contents[0], str): contents[0] = f"{SYSTEM_INSTRUCTION}\n\n{contents[0]}"
                res = client.models.generate_content(model=active_model, contents=contents)
            
            resp_text = res.text

            # ПАРСИНГ ТАБЛИЦЫ (Специально под твой пример)
            if "Дата" in resp_text or "\\t" in resp_text or "\t" in resp_text or "|" in resp_text:
                try:
                    clean_text = resp_text.replace("СДЕЛАЙ В ЭКСЕЛЬ", "").strip()
                    
                    # Если ИИ прислал всё одной строкой с текстовыми \t
                    if "\\t" in clean_text and "\n" not in clean_text:
                        cells = clean_text.split("\\t")
                        # Разбиваем на строки по 4 колонки (как в твоем примере)
                        rows = [cells[i:i+4] for i in range(0, len(cells), 4)]
                    else:
                        # Стандартный разбор
                        lines = [l for l in clean_text.split('\n') if '\t' in l or '|' in l or '  ' in l]
                        rows = []
                        for l in lines:
                            r = l.split('\t') if '\t' in l else [c.strip() for c in l.split('|') if c.strip()]
                            if len(r) > 1: rows.append(r)
                    
                    if rows:
                        df_out = pd.DataFrame(rows)
                        out_io = BytesIO()
                        with pd.ExcelWriter(out_io, engine='openpyxl') as writer:
                            df_out.to_excel(writer, index=False, header=False)
                        st.session_state['last_file'] = out_io.getvalue()
                except: pass

        except Exception as e:
            resp_text = f"Ошибка: {e}"

        st.session_state['chat_history'].append({"role": "assistant", "content": resp_text})
        save_history(st.session_state['chat_history'])
        st.rerun()