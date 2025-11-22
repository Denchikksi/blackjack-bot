import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random

# Токен берём из переменной окружения BOT_TOKEN (в Replit в Secrets)
TOKEN = os.environ["BOT_TOKEN"]

# Игры по chat_id
# chat_id -> {
#   'players': {user_id: {'name', 'hand', 'stand', 'busted'}},
#   'order': [user_id1, user_id2],
#   'turn': int,
#   'started': bool,
#   'finished': bool
# }
games = {}

# Статистика по чатам
# stats[chat_id][user_id] = {'name', 'wins', 'losses', 'draws', 'busts'}
stats = {}

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

def ensure_stats(chat_id: int, user_id: int, name: str):
    if chat_id not in stats:
        stats[chat_id] = {}
    if user_id not in stats[chat_id]:
        stats[chat_id][user_id] = {
            "name": name,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "busts": 0,
        }
    else:
        # обновим имя, если человек переименовался
        stats[chat_id][user_id]["name"] = name

# ---------- КОМАНДЫ ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот Блэкджек 🎰\n\n"
        "Игра 1 на 1 (без дилера), максимум 2 игрока в группе.\n\n"
        "Команды:\n"
        "/newgame – создать новую игру в этом чате\n"
        "/join – присоединиться к игре (до 2 игроков)\n"
        "/startgame – начать игру, когда есть 2 игрока\n"
        "/rematch – реванш с теми же игроками\n"
        "/status – показать текущие карты\n"
        "/stats – твоя статистика в этом чате\n"
        "/top – таблица лидеров чата\n"
        "/cancel – отменить игру"
    )

async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    games[chat_id] = {
        "players": {},
        "order": [],
        "turn": 0,
        "started": False,
        "finished": False,
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

    ensure_stats(chat_id, user_id, user.first_name)

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
    game["finished"] = False
    game["turn"] = 0

    await show_turn(chat_id, context)

async def cmd_rematch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text("Ещё не было игры. Используй /newgame и /startgame.")
        return

    game = games[chat_id]

    if not game["finished"]:
        await update.message.reply_text("Текущая игра ещё не окончена. Сначала доиграйте или /cancel.")
        return

    if len(game["players"]) != 2:
        await update.message.reply_text("Для реванша нужно, чтобы в прошлой игре было 2 игрока.")
        return

    # аналогично старту игры
    for uid, p in game["players"].items():
        p["hand"] = [draw_card(), draw_card()]
        p["stand"] = False
        p["busted"] = False

    game["started"] = True
    game["finished"] = False
    game["turn"] = 0

    await update.message.reply_text("Реванш! Раздаю новые карты 👇")
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

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    if chat_id not in stats or user_id not in stats[chat_id]:
        await update.message.reply_text("У тебя пока нет статистики в этом чате. Сыграй пару игр!")
        return

    s = stats[chat_id][user_id]
    await update.message.reply_text(
        f"Статистика {s['name']} в этом чате:\n"
        f"🏆 Победы: {s['wins']}\n"
        f"😔 Поражения: {s['losses']}\n"
        f"🤝 Ничьи: {s['draws']}\n"
        f"💥 Переборы: {s['busts']}"
    )

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in stats or not stats[chat_id]:
        await update.message.reply_text("В этом чате ещё никто не сыграл. Самое время начать! /newgame")
        return

    players = list(stats[chat_id].values())
    players.sort(key=lambda x: x["wins"], reverse=True)

    lines = ["🏆 Топ игроков по победам:"]
    for i, p in enumerate(players[:10], start=1):
        lines.append(f"{i}. {p['name']} — {p['wins']} побед")

    await update.message.reply_text("\n".join(lines))

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def format_game_state(game):
    lines = []
    for uid in game["order"]:
        p = game["players"][uid]
        s = score(p["hand"])
        status = ""
        if p["busted"]:
            status = " (перебор 💥)"
        elif p["stand"]:
            status = " (стоит)"
        lines.append(f"{p['name']}: {' '.join(p['hand'])} = {s}{status}")
    return "\n".join(lines)

async def show_turn(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
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
        busted = s > 21
        results.append((uid, p["name"], s, busted))
        # учтём перебор в статистике
        if busted:
            ensure_stats(chat_id, uid, p["name"])
            stats[chat_id][uid]["busts"] += 1

    alive = [r for r in results if not r[3]]  # не перебор

    # подготовим текст и обновим wins/losses/draws
    if len(alive) == 0:
        # оба перебор
        result_text = "Оба игрока с перебором 💥\nНичья, оба проиграли 😅"
        # считаем как поражение обоим
        for uid, name, s, busted in results:
            ensure_stats(chat_id, uid, name)
            stats[chat_id][uid]["losses"] += 1
    elif len(alive) == 1:
        r = alive[0]
        winner_id, winner_name, winner_score, _ = r
        loser = [x for x in results if x[0] != winner_id][0]
        loser_id, loser_name, loser_score, _ = loser

        ensure_stats(chat_id, winner_id, winner_name)
        ensure_stats(chat_id, loser_id, loser_name)
        stats[chat_id][winner_id]["wins"] += 1
        stats[chat_id][loser_id]["losses"] += 1

        result_text = (
            f"Победитель: {winner_name} с {winner_score} очками! 🎉\n"
            f"Проиграл: {loser_name} ({loser_score} очков)"
        )
    else:
        a, b = alive[0], alive[1]
        if a[2] > b[2]:
            winner, loser = a, b
        elif b[2] > a[2]:
            winner, loser = b, a
        else:
            # ничья
            ensure_stats(chat_id, a[0], a[1])
            ensure_stats(chat_id, b[0], b[1])
            stats[chat_id][a[0]]["draws"] += 1
            stats[chat_id][b[0]]["draws"] += 1
            result_text = (
                f"Ничья! {a[1]} и {b[1]} оба с {a[2]} очками 🤝"
            )
            state = format_game_state(game)
            text = f"Игра окончена!\n\n{state}\n\n{result_text}"
            await context.bot.send_message(chat_id, text)
            game["started"] = False
            game["finished"] = True
            return

        winner_id, winner_name, winner_score, _ = winner
        loser_id, loser_name, loser_score, _ = loser

        ensure_stats(chat_id, winner_id, winner_name)
        ensure_stats(chat_id, loser_id, loser_name)
        stats[chat_id][winner_id]["wins"] += 1
        stats[chat_id][loser_id]["losses"] += 1

        result_text = (
            f"Победитель: {winner_name} с {winner_score} очками! 🎉\n"
            f"Проиграл: {loser_name} ({loser_score} очков)"
        )

    state = format_game_state(game)
    text = f"Игра окончена!\n\n{state}\n\n{result_text}"

    await context.bot.send_message(chat_id, text)
    game["started"] = False
    game["finished"] = True

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
    app.add_handler(CommandHandler("rematch", cmd_rematch))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CallbackQueryHandler(on_button))

    app.run_polling()

if __name__ == "__main__":
    main()

