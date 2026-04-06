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
from openpyxl.styles import Font

# --- 1. НАСТРОЙКИ ---
load_dotenv()
# Используем os.getenv локально или st.secrets в Streamlit Cloud
api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("API ключ не найден! Проверьте файл .env или Secrets.")

HISTORY_FILE = "chat_history.json"

# ОБНОВЛЕННАЯ ИНСТРУКЦИЯ с **жирным шрифтом**
SYSTEM_INSTRUCTION = """
Ты — профессиональный Excel AI Agent. Твои правила:
1. По команде "СДЕЛАЙ В ЭКСЕЛЬ" выводи данные строго таблицей через ТАБУЛЯЦИЮ (\\t), и никогда не показывай логи или имя команды.
2. Используй **жирный шрифт** (`**`) в Markdown для выделения важных заголовков и терминов в текстовых ответах.
3. Если в исходных данных текст выделен жирным, ставь перед словом '!' (например, !Дата) для Excel, но НЕ используй Markdown (**).
4. Если тебе скинули скриншот, проанализируй его и выведи данные в таблице, указываю его диаграмму ```mermaid и в ```csv
6. Если данных нет, вежливо попроси скриншот или текст, .
7. Если выходит ошибка 529: RESOURCE EXHAUSTED, предложи перейти на **gemini-3.1-flash-lite-preview**.
8. Если ты не знаеш ответ, то переключись на flash-lite-preview. (gemini-3.1-flash-lite-preview)
"""

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Вход в систему")
        password = st.text_input("Пароль", type="password")
        if password == "67": 
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.stop()

check_password()

# Доступные модели
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
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                st.session_state['chat_history'] = json.loads(content) if content else []
        except:
            st.session_state['chat_history'] = []
    else:
        st.session_state['chat_history'] = []

# --- 2. ДИЗАЙН с ГРАДИЕНТОМ ---
st.set_page_config(page_title="Excel AI Agent", layout="wide")
st.markdown("""
    <style>
    /* Градиентный фон с анимацией */
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
    /* Стилизация кнопок */
    .stButton>button {
        background: linear-gradient(90deg, #8E44AD 0%, #3498DB 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: bold;
    }
    /* Полупрозрачные блоки чата и сайдбара */
    [data-testid="stSidebar"], .stDataFrame, .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ИНТЕРФЕЙС ---
with st.sidebar:
    st.title("⚙️ Настройки и Меню")
    st.session_state['selected_model'] = st.selectbox("Выбор модели:", list(MODELS_CONFIG.keys()))
    if st.button("🗑️ Очистить историю чата"):
        st.session_state['chat_history'] = []
        if 'last_file' in st.session_state: del st.session_state['last_file']
        save_history([])
        st.rerun()

st.title("📊 Excel AI Agent")

# Отрисовка чата
for i, msg in enumerate(st.session_state['chat_history']):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        
        # Кнопка скачивания строго под последним ответом ассистента
        if msg["role"] == "assistant" and i == len(st.session_state['chat_history']) - 1:
            if 'last_file' in st.session_state:
                st.download_button(
                    label="📥 СКАЧАТЬ ЭТОТ EXCEL ФАЙЛ",
                    data=st.session_state['last_file'],
                    file_name="agent_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_btn_{i}"
                )

uploaded_file = st.file_uploader("Загрузить данные (Excel или изображение)", type=['xlsx', 'png', 'jpg'])

# --- 4. ЛОГИКА ---
query = st.chat_input("Напишите задачу...")

if query:
    # Очистка старого файла перед новым запросом
    if 'last_file' in st.session_state:
        del st.session_state['last_file']
        
    st.session_state['chat_history'].append({"role": "user", "content": query})
    
    with st.spinner("Агент готовит ответ..."):
        active_model = MODELS_CONFIG[st.session_state['selected_model']]
        
        if uploaded_file:
            if uploaded_file.name.lower().endswith(('.png', '.jpg')):
                contents = [query, Image.open(uploaded_file)]
            else:
                df = pd.read_excel(uploaded_file)
                contents = [f"Таблица:\n{df.to_markdown()}\n\nВопрос: {query}"]
        else:
            contents = [query]

        try:
            # Запрос к API
            if "gemini" in active_model:
                res = client.models.generate_content(model=active_model, contents=contents, config={"system_instruction": SYSTEM_INSTRUCTION})
            else:
                # Gemma-эмуляция системной инструкции
                formatted_prompt = f"{SYSTEM_INSTRUCTION}\n\n{contents[0]}" if isinstance(contents[0], str) else contents[0]
                res = client.models.generate_content(model=active_model, contents=[formatted_prompt] + contents[1:])
            
            resp_text = res.text

            # --- УМНЫЙ ПАРСИНГ И СКРЫТИЕ СЛУЖЕБКИ ---
            if "СДЕЛАЙ В ЭКСЕЛЬ" in resp_text:
                try:
                    parts = resp_text.split("СДЕЛАЙ В ЭКСЕЛЬ")
                    main_answer = parts[0].strip()
                    raw_data = parts[1].strip()

                    # Текст, который увидит пользователь
                    resp_text = main_answer + "\n\n(Excel файл готов к скачиванию ниже)"

                    # Обработка Excel (создание файла)
                    clean_text = raw_data
                    if "\\t" in clean_text or "\t" in clean_text:
                        cells = re.split(r'\\t|\t', clean_text)
                        cells = [c.strip() for c in cells if c.strip()]
                        
                        if cells:
                            col_count = 3 if "Android" in clean_text else 4
                            rows = [cells[i:i+col_count] for i in range(0, len(cells), col_count)]
                            df_out = pd.DataFrame(rows)
                            out_io = BytesIO()
                            with pd.ExcelWriter(out_io, engine='openpyxl') as writer:
                                df_out.to_excel(writer, index=False, header=False, sheet_name='Data')
                                ws = writer.sheets['Data']
                                bold_f = Font(bold=True)
                                for row in ws.iter_rows():
                                    for cell in row:
                                        val = str(cell.value) if cell.value else ""
                                        if val.startswith('!') and not val.startswith('!Срочно'):
                                            cell.value = val[1:] 
                                            cell.font = bold_f
                            st.session_state['last_file'] = out_io.getvalue()
                except Exception as e:
                    resp_text += f"\n\nОшибка парсинга: {e}"

        except Exception as e:
            resp_text = f"Ошибка API: {e}"

        st.session_state['chat_history'].append({"role": "assistant", "content": resp_text})
        save_history(st.session_state['chat_history'])
        st.rerun()