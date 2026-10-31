import os
import sqlite3
from flask import Flask
from threading import Thread
import telebot
from telebot import types

# Flask serveri (Render 24/7 ishlashi uchun)
app = Flask('')

@app.route('/')
def home():
    return "Bot muvaffaqiyatli ishlamoqda!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

Thread(target=run).start()

# --- TELEGRAM BOT SOZLAMALARI ---
BOT_TOKEN = "8714133730:AAE5ppZdITPUPiJ6GehXxHmrVsCJ0EI_srw"
bot = telebot.TeleBot(BOT_TOKEN)

USERS = ["Farrux", "Bexruz", "Temur", "Jalol", "Bunyod"]

# BAZANI TOZALASH UCHUN MAXSUS PIN-KOD
CLEAR_PIN = "1234"

# --- MA'LUMOTLAR BAZASI (SQLite) ---
DB_NAME = "expenses.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payer TEXT,
            amount REAL,
            description TEXT,
            consumers TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Vaqtinchalik kiritish va holat xotirasi (User Session)
user_states = {}

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("➕ Xarajat qo'shish", "📊 Hisobot va Teng bo'lish", "💳 To'lov qilish", "🧹 Bazani tozalash")
    return markup

def get_split_keyboard(selected_users):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for user in USERS:
        status = "✅" if user in selected_users else "❌"
        buttons.append(types.InlineKeyboardButton(f"{status} {user}", callback_data=f"toggle_{user}"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("💾 Xarajatni saqlash", callback_data="save_expense"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        f"Xush kelibsiz, {message.from_user.first_name}!\n"
        "Xarajatlarni hisoblash va to'lovlarni boshqarish botiga xush kelibsiz.\n"
        "Quyidagi tugmalardan foydalaning:",
        reply_markup=get_main_keyboard()
    )

# --- XARAJAT QO'SHISH BO'LIMI ---
@bot.message_handler(func=lambda msg: msg.text == "➕ Xarajat qo'shish")
def start_add_expense(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for user in USERS:
        markup.add(types.InlineKeyboardButton(user, callback_data=f"payer_{user}"))
    bot.send_message(message.chat.id, "Pul to'lagan odamni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("payer_"))
def process_payer(call):
    payer = call.data.split("_")[1]
    user_states[call.message.chat.id] = {"payer": payer}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"To'lovchi: {payer}.\nXarajat summasini kiriting (masalan: 50000):")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and "amount" not in user_states[msg.chat.id] and user_states[msg.chat.id].get("state") not in ["awaiting_pin", "awaiting_receipt"])
def process_amount(message):
    try:
        amount = float(message.text.replace(',', '.'))
        user_states[msg.chat.id]["amount"] = amount
        bot.send_message(message.chat.id, "Xarajat haqida qisqacha izoh kiriting (masalan: Tushlik yoki Taksi):")
    except ValueError:
        bot.send_message(message.chat.id, "Iltimos, faqat raqam kiriting! Masalan: 50000")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and "amount" in user_states[msg.chat.id] and "description" not in user_states[msg.chat.id] and user_states[msg.chat.id].get("state") not in ["awaiting_pin", "awaiting_receipt"])
def process_description(message):
    user_states[msg.chat.id]["description"] = message.text
    user_states[msg.chat.id]["consumers"] = USERS.copy()
    
    bot.send_message(
        message.chat.id,
        "Ushbu xarajat kimlar uchun bo'ldi?\n(Ismlarni bosing, tanlab bo'lgach **'💾 Xarajatni saqlash'** bosing):",
        reply_markup=get_split_keyboard(user_states[msg.chat.id]["consumers"]),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_"))
def process_toggle(call):
    chat_id = call.message.chat.id
    if chat_id not in user_states or "consumers" not in user_states[chat_id]:
        bot.answer_callback_query(call.id, "Sessiya eskirgan. Qaytadan boshlang.")
        return

    user = call.data.split("_")[1]
    consumers = user_states[chat_id]["consumers"]

    if user in consumers:
        if len(consumers) > 1:
            consumers.remove(user)
        else:
            bot.answer_callback_query(call.id, "Kamida 1 ta odam tanlanishi kerak!", show_alert=True)
            return
    else:
        consumers.append(user)

    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=get_split_keyboard(consumers)
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "save_expense")
def process_save(call):
    chat_id = call.message.chat.id
    if chat_id not in user_states or "amount" not in user_states[chat_id]:
        bot.answer_callback_query(call.id, "Xatolik yuz berdi. Qaytadan boshlang.")
        return

    state = user_states[chat_id]
    payer = state["payer"]
    amount = state["amount"]
    desc = state["description"]
    consumers = ",".join(state["consumers"])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (payer, amount, description, consumers) VALUES (?, ?, ?, ?)",
        (payer, amount, desc, consumers)
    )
    conn.commit()
    conn.close()

    del user_states[chat_id]

    bot.answer_callback_query(call.id, "Xarajat saqlandi!")
    bot.send_message(
        chat_id,
        f"✅ **Xarajat saqlandi!**\n\n"
        f"👤 To'ladi: **{payer}**\n"
        f"💰 Summa: **{amount:,.0f} so'm**\n"
        f"📝 Izoh: **{desc}**\n"
        f"👥 Bo'lishuvchilar: **{consumers.replace(',', ', ')}**",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# --- HISOBOT BO'LIMI ---
@bot.message_handler(func=lambda msg: msg.text == "📊 Hisobot va Teng bo'lish")
def show_report(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT payer, amount, description, consumers FROM
