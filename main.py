from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random

import os
TOKEN = os.environ["BOT_TOKEN"]
# Игры по chat_id
games = {}  # chat_id -> { 'players': {user_id: {...}, ...}, 'order': [...], 'turn': int, 'started': bool }

# Визуальные карты Unicode
cards = [
    "🂡","🂢","🂣","🂤","🂥","🂦","🂧","🂨","🂩","🂪","🂫","🂭","🂮",  # ♠
    "🂱","🂲","🂳","🂴","🂵","🂶","🂷","🂸","🂹","🂺","🂻","🂽","🂾",  # ♥
    "🃁","🃂","🃃","🃄","🃅","🃆","🃇","🃈","🃉","🃊","🃋","🃍","🃎",  # ♦
    "🃑","🃒","🃓","🃔","🃕","🃖","🃗","🃘","🃙","🃚","🃛","🃝","🃞"   # ♣
]

def card_value(card: str) -> int:
    idx = cards.index(card) % 13 + 1
    if idx == 1:
        return 11          # туз
    if idx > 10:
        return 10          # J Q K
    return idx             # 2–10

def score(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if card_value(c) == 11)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def draw_card():
    return random.choice(cards)

def keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Hit 🃏", callback_data="hit"),
          InlineKeyboardButton("Stand ✋", callback_data="stand")]]
    )

# ---------- КОМАНДЫ ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот Блэкджек 🎰\n\n"
        "Игра 1 на 1 (без дилера), максимум 2 игрока в группе.\n\n"
        "Команды:\n"
        "/newgame – создать новую игру в этом чате\n"
        "/join – присоединиться к игре (до 2 игроков)\n"
        "/startgame – начать игру, когда есть 2 игрока\n"
        "/status – показать текущие карты\n"
        "/cancel – отменить игру"
    )

async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in games and games[chat_id]["started"]:
        await update.message.reply_text("Игра уже идёт в этом чате. Дождитесь окончания или /cancel.")
        return

    games[chat_id] = {
        "players": {},   # user_id -> { 'name': str, 'hand': [...], 'stand': bool, 'busted': bool }
        "order": [],
        "turn": 0,
        "started": False
    }
    await update.message.reply_text(
        "Создана новая игра!\nИгроки могут присоединиться командой /join.\nМаксимум 2 игрока."
    )

async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    if chat_id not in games:
        await update.message.reply_text("Сначала создайте игру командой /newgame.")
        return

    game = games[chat_id]

    if game["started"]:
        await update.message.reply_text("Игра уже началась, присоединиться нельзя.")
        return

    if user_id in game["players"]:
        await update.message.reply_text("Ты уже участвуешь в этой игре.")
        return

    if len(game["players"]) >= 2:
        await update.message.reply_text("В этой игре уже 2 игрока, мест нет.")
        return

    game["players"][user_id] = {
        "name": user.first_name,
        "hand": [],
        "stand": False,
        "busted": False
    }
    game["order"].append(user_id)

    await update.message.reply_text(f"{user.first_name} присоединился к игре!")

    if len(game["players"]) == 2:
        await update.message.reply_text("2 игрока готовы! Напишите /startgame чтобы начать.")

async def cmd_startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text("Сначала создайте игру командой /newgame.")
        return

    game = games[chat_id]

    if game["started"]:
        await update.message.reply_text("Игра уже началась.")
        return

    if len(game["players"]) < 2:
        await update.message.reply_text("Для игры нужно 2 игрока. Пусть второй сделает /join.")
        return

    # Раздаём по 2 карты каждому
    for uid, p in game["players"].items():
        p["hand"] = [draw_card(), draw_card()]
        p["stand"] = False
        p["busted"] = False

    game["started"] = True
    game["turn"] = 0

    await show_turn(chat_id, context)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games or not games[chat_id]["started"]:
        await update.message.reply_text("Сейчас нет активной игры. /newgame чтобы создать.")
        return

    game = games[chat_id]
    text = format_game_state(game)
    await update.message.reply_text(text)

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text("Игра не найдена.")
        return

    del games[chat_id]
    await update.message.reply_text("Игра отменена.")

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def format_game_state(game):
    lines = []
    for uid in game["order"]:
        p = game["players"][uid]
        s = score(p["hand"])
        status = " (стоит)" if p["stand"] else ""
        if p["busted"]:
            status = " (перебор 💥)"
        lines.append(f"{p['name']}: {' '.join(p['hand'])} = {s}{status}")
    return "\n".join(lines)

async def show_turn(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Показываем текущую ситуацию и чей ход."""
    game = games[chat_id]
    turn_idx = game["turn"]
    current_id = game["order"][turn_idx]
    current_player = game["players"][current_id]

    text = (
        "Текущее состояние игры:\n\n"
        f"{format_game_state(game)}\n\n"
        f"Сейчас ход: {current_player['name']}"
    )

    await context.bot.send_message(chat_id, text, reply_markup=keyboard())

def all_players_done(game):
    for uid in game["order"]:
        p = game["players"][uid]
        if not p["stand"] and not p["busted"]:
            return False
    return True

async def finish_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games[chat_id]

    results = []
    for uid in game["order"]:
        p = game["players"][uid]
        s = score(p["hand"])
        if s > 21:
            results.append((uid, p["name"], s, True))   # busted
        else:
            results.append((uid, p["name"], s, False))

    # Определяем победителя
    alive = [r for r in results if not r[3]]  # не перебор
    if len(alive) == 0:
        result_text = "Оба игрока с перебором 💥\nНичья, оба проиграли 😅"
    elif len(alive) == 1:
        r = alive[0]
        result_text = (
            f"Победитель: {r[1]} с {r[2]} очками! 🎉\n\n"
        )
    else:
        # два живых — сравниваем очки
        a, b = alive[0], alive[1]
        if a[2] > b[2]:
            result_text = f"Победитель: {a[1]} с {a[2]} очками! 🎉\nПроиграл: {b[1]} ({b[2]} очков)"
        elif b[2] > a[2]:
            result_text = f"Победитель: {b[1]} с {b[2]} очками! 🎉\nПроиграл: {a[1]} ({a[2]} очков)"
        else:
            result_text = (
                f"Ничья! {a[1]} и {b[1]} оба с {a[2]} очками 🤝"
            )

    state = format_game_state(game)
    text = f"Игра окончена!\n\n{state}\n\n{result_text}"

    await context.bot.send_message(chat_id, text)
    del games[chat_id]

# ---------- КНОПКИ (Hit / Stand) ----------

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    if chat_id not in games:
        await query.edit_message_text("Игра уже закончена или не создана. /newgame чтобы начать новую.")
        return

    game = games[chat_id]

    if not game["started"]:
        await query.edit_message_text("Игра ещё не началась. Напишите /startgame.")
        return

    if user_id not in game["players"]:
        await query.answer("Ты не участвуешь в этой игре.", show_alert=True)
        return

    # Проверяем очередь
    current_id = game["order"][game["turn"]]
    if user_id != current_id:
        await query.answer("Сейчас ход другого игрока!", show_alert=True)
        return

    player = game["players"][user_id]

    if query.data == "hit":
        player["hand"].append(draw_card())
        s = score(player["hand"])
        if s > 21:
            player["busted"] = True
            text = (
                f"{player['name']} взял карту: {player['hand'][-1]}\n"
                f"{player['name']}: {' '.join(player['hand'])} = {s} (перебор 💥)\n\n"
                "Ход переходит к следующему игроку."
            )
            await query.edit_message_text(text)
        else:
            # игрок может ещё ходить, не меняем очередь
            text = (
                f"{player['name']} взял карту: {player['hand'][-1]}\n"
                f"{player['name']}: {' '.join(player['hand'])} = {s}\n\n"
                "Жми Hit или Stand."
            )
            await query.edit_message_text(text, reply_markup=keyboard())
            return  # тот же игрок ходит дальше

    elif query.data == "stand":
        player["stand"] = True
        text = (
            f"{player['name']} остановился.\n"
            f"{player['name']}: {' '.join(player['hand'])} = {score(player['hand'])}\n\n"
            "Ход переходит к следующему игроку."
        )
        await query.edit_message_text(text)

    # Проверяем, все ли закончили
    if all_players_done(game):
        await finish_game(chat_id, context)
        return

    # Переходим к следующему игроку
    while True:
        game["turn"] = (game["turn"] + 1) % len(game["order"])
        next_id = game["order"][game["turn"]]
        next_p = game["players"][next_id]
        if not next_p["stand"] and not next_p["busted"]:
            break

    await show_turn(chat_id, context)

# ---------- ЗАПУСК ----------

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("startgame", cmd_startgame))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_button))

    app.run_polling()

if __name__ == "__main__":
    main()
