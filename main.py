import os
import sqlite3
import threading
import time
from flask import Flask
import telebot
from telebot.apihelper import ApiTelegramException

# ==========================================
# ЧАСТЬ 1: НАСТРОЙКА БОТА И ПЕРЕМЕННЫХ
# ==========================================
# ВНИМАНИЕ! Аккуратно сотри текст внутри кавычек ниже и вставь свой токен:
TOKEN = "8955717735:AAEB6fi66bZXd6ff4ab31NeQqUWL5T5VSrI"
bot = telebot.TeleBot()

# Хранилище сессий пользователей (для Единого Окна)
user_sessions = {}

# ==========================================
# ЧАСТЬ 2: ЗАЗАЩИТА ОТ ЗАСЫПАНИЯ (FLASK СЕРВЕР)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает и защищен от засыпания!", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Запускаем Flask-сервер в отдельном фоновом потоке
threading.Thread(target=run_server, daemon=True).start()

# ==========================================
# ЧАСТЬ 3: БАЗА ДАННЫХ (SQLite)
# ==========================================
def init_db():
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS businesses 
                          (name TEXT PRIMARY KEY, ads_high INTEGER, ads_low INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS goods 
                          (id INTEGER PRIMARY KEY AUTOINCREMENT, biz_name TEXT, name TEXT, photo TEXT, price REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS employees 
                          (code TEXT PRIMARY KEY, name TEXT, role TEXT, balance REAL)''')
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM businesses")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO businesses VALUES (?, ?, ?)", 
                               [("Туи", 0, 0), ("Заборы", 0, 0), ("Теплицы", 0, 0)])
            cursor.execute("INSERT INTO employees VALUES (?, ?, ?, ?)", ("10", "Тестовый Работник", "employee", 0.0))
            conn.commit()

# ==========================================
# ЧАСТЬ 4: ЛОГИКА ЕДИНОГО ОКНА (UI) И КОМАНДЫ
# ==========================================
def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "menu_msg_id": None,
            "role": None,
            "state": "AWAITING_PASS"
        }
    return user_sessions[chat_id]

def send_or_edit_menu(chat_id, text, reply_markup=None):
    session = get_session(chat_id)
    try:
        if session["menu_msg_id"]:
            bot.edit_message_text(text, chat_id, session["menu_msg_id"], reply_markup=reply_markup)
        else:
            msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
            session["menu_msg_id"] = msg.message_id
    except ApiTelegramException:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
        session["menu_msg_id"] = msg.message_id

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except ApiTelegramException:
        pass
        
    session = get_session(chat_id)
    session["state"] = "AWAITING_PASS"
    session["role"] = None
    
    send_or_edit_menu(chat_id, "👋 Добро пожаловать!\n\nВведите пароль администратора (123) или личный код сотрудника:")

# ==========================================
# ЧАСТЬ 5: ОБРАБОТКА callback_query И ТЕКСТА
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text
    session = get_session(chat_id)

    try:
        bot.delete_message(chat_id, message.message_id)
    except ApiTelegramException:
        pass

    if session["state"] == "AWAITING_PASS":
        if text == "123":
            session["role"] = "admin"
            session["state"] = "MAIN_MENU"
            
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("Открыть Mini App", text="В разработке")) 
            
            send_or_edit_menu(chat_id, "🔓 Вы вошли как Администратор!\n\nИспользуйте меню или откройте веб-панель:", reply_markup=markup)
        else:
            with sqlite3.connect("bot_database.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM employees WHERE code = ?", (text,))
                row = cursor.fetchone()
                
                if row:
                    session["role"] = "employee"
                    session["state"] = "MAIN_MENU"
                    send_or_edit_menu(chat_id, f"👤 Добро пожаловать, {row[0]}!\n\nВаш личный кабинет успешно открыт.")
                else:
                    send_or_edit_menu(chat_id, "❌ Неверный пароль или код.\n\nПопробуйте ввести заново:")

# ==========================================
# ЧАСТЬ 6: ЗАПУСК
# ==========================================
if __name__ == '__main__':
    init_db()
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)
