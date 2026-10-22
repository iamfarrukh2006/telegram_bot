import os
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot ishlamoqda!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

Thread(target=run).start()

import datetime
import telebot
from telebot import types

TOKEN = '8714133730:AAHmvdF9wRpbsbk_vQFVOeZw-5_wW3xQigU'
bot = telebot.TeleBot(TOKEN)

# Doimiy 5 ta ishtirokchi
FRIENDS = ["Farrux", "Behruz", "Temur", "Jalol", "Bunyod"]

# Ma'lumotlarni saqlash (Chat ID bo'yicha)
data = {}

def get_chat_data(chat_id):
    if chat_id not in data:
        data[chat_id] = {
            'expenses': [],  # Xarajatlar ro'yxati
            'temp_expense': {} # Vaqtincha kiritilayotgan xarajat ma'lumotlari
        }
    return data[chat_id]

# Asosiy menyu
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("➕ Xarajat qo'shish")
    btn2 = types.KeyboardButton("📊 Hisobot va Teng bo'lish")
    btn3 = types.KeyboardButton("📜 Xarajatlar tarixi")
    btn4 = types.KeyboardButton("🗑 Tarixni tozalash")
    markup.add(btn1, btn2, btn3, btn4)
    return markup


@bot.message_handler(commands=['start'])
def start_cmd(message):
    get_chat_data(message.chat.id)
    text = (
        "👋 **Xarajatlarni Boshqarish Botiga Xush Kelibsiz!**\n\n"
        "Bu bot 5 ta do'st ({}) o'rtasidagi xarajatlarni adolatli taqsimlaydi.\n"
        "Kerakli bo'limni tanlang 👇".format(", ".join(FRIENDS))
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard(), parse_mode='Markdown')


# 1. XARAJAT QO'SHISH - ISM TANLASH
@bot.message_handler(func=lambda m: m.text == "➕ Xarajat qo'shish")
def add_expense_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name in FRIENDS:
        markup.add(types.InlineKeyboardButton(name, callback_data=f"payer_{name}"))

    bot.send_message(message.chat.id, "💰 Pulni sarflagan kishini tanlang:", reply_markup=markup)


# Ism tanlangandan keyingi qadam (Inline tugma bosilganda)
@bot.callback_query_handler(func=lambda call: call.data.startswith("payer_"))
def callback_payer(call):
    payer_name = call.data.split("_")[1]
    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        f"👤 Tanlandi: **{payer_name}**\n\nQancha summa sarflaganini kiriting (masalan: `120000`):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_amount, payer_name)


def process_amount(message, payer_name):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError

        msg = bot.send_message(message.chat.id, "📝 Xarajat izohini kiriting (masalan: `Osh`, `Taksi`, `Bozorlik`):",
                               parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_comment, payer_name, amount)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Noto'g'ri summa. Faqat raqam kiriting!")


def process_comment(message, payer_name, amount):
    comment = message.text
    chat_id = message.chat.id
    chat_data = get_chat_data(chat_id)
    
    # Vaqtincha ma'lumotni saqlab turamiz
    chat_data['temp_expense'] = {
        'payer': payer_name,
        'amount': amount,
        'comment': comment,
        'consumers': FRIENDS.copy() # Boshlang'ich holatda hamma tanlangan bo'ladi
    }

    # Kimlar uchunligi tanlash uchun inline tugmalar (Birma-bir yoqib/o'chirish uchun)
    markup = get_split_keyboard(chat_data['temp_expense']['consumers'])

    bot.send_message(
        chat_id,
        f"Tanlang: {payer_name} qilgan {amount:,.0f} so'mlik xarajat kimlarga bo'linsin?\n(Kerakli odam ustiga bosib o'chiring yoki qoldiring, so'ng saqlang):",
        reply_markup=markup,
        parse_mode='Markdown'
    )


def get_split_keyboard(selected_users):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for name in FRIENDS:
        icon = "✅" if name in selected_users else "❌"
        markup.add(types.InlineKeyboardButton(f"{icon} {name}", callback_data=f"toggle_{name}"))
    
    markup.add(types.InlineKeyboardButton("💾 Xarajatni saqlash", callback_data="save_expense"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_"))
def callback_toggle_consumer(call):
    bot.answer_callback_query(call.id)
    name = call.data.split("_")[1]
    chat_id = call.message.chat.id
    chat_data = get_chat_data(chat_id)
    
    if 'temp_expense' not in chat_data:
        bot.send_message(chat_id, "⚠️ Xatolik yuz berdi. Iltimos, xarajatni qaytadan qo'shing.")
        return

    consumers = chat_data['temp_expense']['consumers']
    if name in consumers:
        if len(consumers) == 1:
            bot.answer_callback_query(call.id, "⚠️ Kamida 👤 bitta odam qolishi kerak!", show_alert=True)
            return
        consumers.remove(name)
    else:
        consumers.append(name)

    # Tugmalarni yangilaymiz
    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=get_split_keyboard(consumers)
    )


@bot.callback_query_handler(func=lambda call: call.data == "save_expense")
def callback_save_expense(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chat_data = get_chat_data(chat_id)

    if 'temp_expense' not in chat_data or not chat_data['temp_expense']:
        bot.send_message(chat_id, "⚠️ Saqlash uchun ma'lumot topilmadi.")
        return

    exp = chat_data['temp_expense']
    today = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    chat_data['expenses'].append({
        'payer': exp['payer'],
        'amount': exp['amount'],
        'comment': exp['comment'],
        'consumers': exp['consumers'],
        'date': today
    })

    consumers_str = ", ".join(exp['consumers'])
    bot.edit_message_text(
        f"✅ **Xarajat muvaffaqiyatli saqlandi!**\n\n"
        f"👤 Kim to'ladi: **{exp['payer']}**\n"
        f"💰 Summa: **{exp['amount']:,.0f} so'm**\n"
        f"📝 Izoh: {exp['comment']}\n"
        f"👥 Kimlar uchun: **{consumers_str}**\n"
        f"📅 Sana: {today}",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode='Markdown'
    )
    # Vaqtinchalik xotirani tozalaymiz
    chat_data['temp_expense'] = {}


# 2. XARAJATLAR TARIXI
@bot.message_handler(func=lambda m: m.text == "📜 Xarajatlar tarixi")
def show_history(message):
    chat_data = get_chat_data(message.chat.id)
    expenses = chat_data['expenses']

    if not expenses:
        bot.send_message(message.chat.id, "📜 Hali hech qanday xarajat kiritilmadi.")
        return

    text = "📜 **Kiritilgan xarajatlar tarixi:**\n\n"
    for i, exp in enumerate(expenses, 1):
        consumers_str = ", ".join(exp['consumers'])
        text += f"{i}. **{exp['payer']}** - {exp['amount']:,.0f} so'm ({exp['comment']})\n   👥 Kimlar uchun: {consumers_str}\n   📅 {exp['date']}\n\n"

    bot.send_message(message.chat.id, text, parse_mode='Markdown')


# 3. HISOBOT VA TENG BO'LISH
@bot.message_handler(func=lambda m: m.text == "📊 Hisobot va Teng bo'lish")
def calculate_report(message):
    chat_data = get_chat_data(message.chat.id)
    expenses = chat_data['expenses']

    if not expenses:
        bot.send_message(message.chat.id, "❌ Hali xarajatlar kiritilmagani uchun hisobot mavjud emas.")
        return

    paid_totals = {name: 0.0 for name in FRIENDS}
    net_balance = {name: 0.0 for name in FRIENDS}
    total_spent = 0

    for exp in expenses:
        payer = exp['payer']
        amount = exp['amount']
        consumers = exp['consumers']

        total_spent += amount
        paid_totals[payer] += amount

        share = amount / len(consumers)
        for consumer in consumers:
            net_balance[payer] += share  
            net_balance[consumer] -= share  

    report = f"📊 **ADOLATLI HISOBOT VA TAQSIMOT**\n"
    report += f"➖➖➖➖➖➖➖➖➖➖\n"
    report += f"💰 **Jami xarajat:** {total_spent:,.0f} so'm\n\n"

    report += f"👤 **Kim qancha pul sarfladi:**\n"
    for name in FRIENDS:
        report += f"• **{name}**: {paid_totals[name]:,.0f} so'm\n"

    report += f"\n⚖️ **Qarzlar va O'zaro Hisob-kitob:**\n"

    debtors = []
    creditors = []

    for name, bal in net_balance.items():
        if bal < -0.01:
            debtors.append([name, -bal])  
        elif bal > 0.01:
            creditors.append([name, bal])  

    if not debtors and not creditors:
        report += "⚪️ Hamma hisob-kitob toza! Qarzdorlar yo'q.\n"
    else:
        for debtor in debtors:
            report += f"🔴 **{debtor[0]}** umumiy hisobga **{debtor[1]:,.0f} so'm** to'lashi/berishi kerak.\n"
        for creditor in creditors:
            report += f"🟢 **{creditor[0]}** umumiy hisobdan **{creditor[1]:,.0f} so'm** olishi kerak.\n"

    bot.send_message(message.chat.id, report, parse_mode='Markdown')


# 4. TARIXNI TOZALASH
@bot.message_handler(func=lambda m: m.text == "🗑 Tarixni tozalash")
def clear_history_prompt(message):
    today_code = datetime.datetime.now().strftime("%Y%m%d")  
    msg = bot.send_message(
        message.chat.id,
        "⚠️ Tarixni tozalash uchun maxfiy kodni kiriting\n"
        "(Maxfiy kod **bugungi sana** yil-oy-kun formatida, masalan: `YYYYMMDD`):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_clear_code, today_code)


def process_clear_code(message, correct_code):
    user_input = message.text.strip()
    chat_data = get_chat_data(message.chat.id)

    if user_input == correct_code:
        chat_data['expenses'] = []
        bot.send_message(message.chat.id, "🧹 Muvaffaqiyatli! Barcha xarajatlar tarixi tozalandi.")
    else:
        bot.send_message(message.chat.id, "❌ Xato kod! Tarix tozalanmadi.")


print("Bot muvaffaqiyatli ishga tushdi...")
bot.infinity_polling()
