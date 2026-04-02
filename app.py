import streamlit as st
import pandas as pd
from google import genai
from PIL import Image
from dotenv import load_dotenv
import os
import io
import json
import streamlit.components.v1 as components

# --- 1. НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("API ключ не найден! Проверьте файл .env")

HISTORY_FILE = "chat_history.json"
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Вход в приложение")
        st.write("Для доступа к приложению введите пароль")
        password = st.text_input("Введите пароль доступа", type="password")
        st.divider()
        st.title("⭐ Удачного дня! 😀")
        if password == "oyijonim67": # Твой пароль
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.stop() # Останавливает выполнение кода дальше

check_password()

# Конфигурация моделей
MODELS_CONFIG = {
    "💎 Gemma 3 27B (14.4K/день)": "gemma-3-27b-it",
    "⚡ 3.1 Flash Lite (500/день)": "gemini-3.1-flash-lite-preview",
    "🚀 Gemini 3 Flash (20/день)": "gemini-3-flash-preview",
}

# Инициализация состояний
if 'selected_model' not in st.session_state:
    st.session_state['selected_model'] = "💎 Gemma 3 27B (14.4K/день)"

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = load_history()

# --- 2. ФУНКЦИИ ИИ ---
def analyze_with_gemini(prompt, file=None):
    try:
        # АВТО-ПЕРЕКЛЮЧЕНИЕ:
        if file is None:
            # Если файла нет, всегда используем Gemma для экономии (14.4K лимита)
            model_id = "gemma-3-27b-it"
            status_msg = "🤖 Работаю в режиме текста (Gemma 3)"
        else:
            # Если файл есть, берем выбранную тобой модель (Gemini)
            model_id = MODELS_CONFIG[st.session_state['selected_model']]
            status_msg = f"👁️ Анализирую файл через {st.session_state['selected_model']}"
        
        # Вывод технической инфо в консоль (для тебя)
        print(f"DEBUG: Using {model_id}")

        if file:
            img = Image.open(file)
            response = client.models.generate_content(model=model_id, contents=[prompt, img])
        else:
            response = client.models.generate_content(model=model_id, contents=[prompt])
            
        return response.text
    except Exception as e:
        return f"Ошибка ИИ: {e}"

# --- 3. ДИЗАЙН И ФОН ---
st.set_page_config(page_title="Excel AI Agent", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        /* Находим контейнер ввода и само поле */
    [data-testid="stChatInput"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(161, 85, 193, 0.3) !important; /* Тонкая фиалковая рамка */
        border-radius: 15px !important;
        backdrop-filter: blur(10px) !important;
    }
    
    /* Исправляем цвет текста внутри, если он стал плохо виден */
    [data-testid="stChatInput"] textarea {
        color: #FFFFFF !important;
        background-color: transparent !important;
    }
    
    /* Делаем нижнюю плашку (где находится инпут) прозрачной */
    .stChatFloatingInputContainer {
        background-color: transparent !important;
        bottom: 20px !important; /* Немного приподнимем для красоты */
    }
    /* 1. АНИМИРОВАННЫЙ ГРАДИЕНТ НА ВЕСЬ ЭКРАН */
    .stApp {
        background: linear-gradient(-45deg, #1A0B2E, #031D44, #4D194D, #003366) !important;
        background-size: 400% 400% !important;
        animation: gradient 15s ease infinite !important;
        height: 100vh;
    }

    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* 2. ЭФФЕКТ СТЕКЛА (Glassmorphism) */
    [data-testid="stSidebar"], .stDataFrame, [data-testid="stMetric"], .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
    }

    /* 3. КНОПКИ */
    .stButton>button {
        background: linear-gradient(90deg, #8E44AD 0%, #3498DB 100%) !important;
        color: white !important;
        border: none !important;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 20px rgba(142, 68, 173, 0.5);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.title("⚙️ Настройки")
    st.write(f"Текущая модель: **{st.session_state['selected_model']}**")
    
    if st.button("🗑️ Очистить чат"):
        st.session_state['chat_history'] = []
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        st.rerun()
    
    st.divider()
    st.title("📜 История")
    for msg in reversed(st.session_state['chat_history']):
        if msg["role"] == "user":
            st.caption(f"🔍 {msg['content'][:40]}...")

# --- 5. ОСНОВНОЙ ИНТЕРФЕЙС ---
st.title("📊 Excel AI Agent")

for message in st.session_state['chat_history']:
    with st.chat_message(message["role"]):
        st.write(message["content"])

uploaded_file = st.file_uploader("Загрузите отчет (Картинка или Excel)", type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'])

if uploaded_file:
    if uploaded_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
        st.image(uploaded_file, caption="Файл загружен", use_container_width=True)
    else:
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(5))

# --- 6. УМНАЯ ЛОГИКА (Авто-выбор модели) ---
user_query = st.chat_input("Напишите агенту или команду (/model, /stats, /undo)...")

if user_query:
    # 1. ОБРАБОТКА СИСТЕМНЫХ КОМАНД
    if user_query.startswith("/"):
        parts = user_query.split()
        cmd = parts[0].lower()

        if cmd == "/model":
            if len(parts) > 1:
                target = parts[1]
                found = False
                for full_name in MODELS_CONFIG.keys():
                    if target in full_name:
                        st.session_state['selected_model'] = full_name
                        st.success(f"✅ Для файлов выбрана модель: {full_name}")
                        found = True
                        break
                if not found:
                    st.error("Модель не найдена. Попробуйте: 27, 3.1 или 3")
            else:
                st.info(f"Доступные модели для файлов: {', '.join(MODELS_CONFIG.keys())}")
        
        elif cmd == "/stats":
            st.info("📊 Лимиты: Gemma (текст) — 14.4K/день. Gemini 3.1 (файлы) — 500/день.")
        
        elif cmd == "/undo":
            if len(st.session_state['chat_history']) >= 2:
                st.session_state['chat_history'].pop()
                st.session_state['chat_history'].pop()
                save_history(st.session_state['chat_history'])
                st.success("Последняя реплика удалена")
            else:
                st.warning("История пуста")
        
        else:
            st.warning("Доступны: /model, /stats, /undo")
        
        st.rerun()

    # 2. ОБЫЧНЫЙ ЗАПРОС К ИИ
    else:
        st.session_state['chat_history'].append({"role": "user", "content": user_query})
        
        with st.spinner("Агент подбирает оптимальную модель..."):
            # Авто-выбор на лету:
            if uploaded_file is None:
                # Текст без файлов — всегда Gemma (макс. экономия)
                active_model = "gemma-3-27b-it"
                mode_info = "⚡ Mode: Text-only (Gemma)"
            else:
                # Есть файл — используем мощную Gemini из настроек
                active_model = MODELS_CONFIG[st.session_state['selected_model']]
                mode_info = f"👁️ Mode: Vision ({st.session_state['selected_model']})"
            
            # Вызываем функцию ИИ, передавая выбранную модель напрямую
            try:
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    response = client.models.generate_content(model=active_model, contents=[user_query, img])
                else:
                    response = client.models.generate_content(model=active_model, contents=[user_query])
                
                response_text = response.text
                # Добавляем пометку, какая модель ответила (по желанию можно убрать)
                # response_text = f"*{mode_info}*\n\n{response_text}"
                
            except Exception as e:
                response_text = f"Ошибка ИИ: {e}"

            st.session_state['chat_history'].append({"role": "assistant", "content": response_text})
            save_history(st.session_state['chat_history'])
            st.rerun()