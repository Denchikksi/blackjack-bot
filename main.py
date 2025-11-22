import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Токен берём из переменной окружения BOT_TOKEN (в Replit → Secrets)
TOKEN = os.environ["BOT_TOKEN"]

START_BALANCE = 1000  # стартовые фишки

# ===== ДАННЫЕ ПО ИГРЕ, СТАТЕ И БАЛАНСАМ =====

# games[chat_id] = {
#   'players': {user_id: {'name', 'hand', 'stand', 'busted', 'bet'}},
#   'order': [user_id1, user_id2],
#   'turn': int,
#   'started': bool,
#   'finished': bool
# }
games = {}

# stats[chat_id][user_id] = {'name', 'wins', 'losses', 'draws', 'busts'}
stats = {}

# balances[chat_id][user_id] = {'name', 'balance'}
balances = {}

# Визуальные карты Unicode
cards = [
    "🂡","🂢","🂣","🂤","🂥","🂦","🂧","🂨","🂩","🂪","🂫","🂭","🂮",
    "🂱","🂲","🂳","🂴","🂵","🂶","🂷","🂸","🂹","🂺","🂻","🂽","🂾",
    "🃁","🃂","🃃","🃄","🃅","🃆","🃇","🃈","🃉","🃊","🃋","🃍","🃎",
    "🃑","🃒","🃓","🃔","🃕","🃖","🃗","🃘","🃙","🃚","🃛","🃝","🃞"
]

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def card_value(card: str) -> int:
    idx = cards.index(card) % 13 + 1
    if idx == 1:
        return 11      # туз
    if idx > 10:
        return 10      # J,Q,K
    return idx         # 2–10

def score(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if card_value(c) == 11)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def draw_card():
    return random.choice(cards)

def turn_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Hit 🃏", callback_data="hit"),
          InlineKeyboardButton("Stand ✋", callback_data="stand")]]
    )

def ensure_stats(chat_id: int, user_id: int, name: str):
    chat_stats = stats.setdefault(chat_id, {})
    user_stats = chat_stats.get(user_id)
    if not user_stats:
        chat_stats[user_id] = {
            "name": name,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "busts": 0,
        }
    else:
        user_stats["name"] = name

def ensure_balance(chat_id: int, user_id: int, name: str):
    chat_balances = balances.setdefault(chat_id, {})
    user_bal = chat_balances.get(user_id)
    if not user_bal:
        chat_balances[user_id] = {"name": name, "balance": START_BALANCE}
    else:
        user_bal["name"] = name

def format_game_state(game):
    lines = []
    for uid in game["order"]:
        p = game["players"][uid]
        s = score(p["hand"]) if p["hand"] else 0
        status = ""
        if p["busted"]:
            status = " (перебор 💥)"
        elif p["stand"]:
            status = " (стоит)"
        bet_info = f", ставка: {p['bet']}" if p["bet"] else ""
        cards_str = " ".join(p["hand"]) if p["hand"] else "—"
        lines.append(f"{p['name']}: {cards_str} = {s}{status}{bet_info}")
    return "\n".join(lines)

async def show_turn(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games[chat_id]
    current_id = game["order"][game["turn"]]
    current_player = game["players"][current_id]
    text = (
        "Текущее состояние игры:\n\n"
        f"{format_game_state(game)}\n\n"
        f"Сейчас ход: {current_player['name']}"
    )
    await context.bot.send_message(chat_id, text, reply_markup=turn_keyboard())

def all_players_done(game):
    for uid in game["order"]:
        p = game["players"][uid]
        if not p["stand"] and not p["busted"]:
            return False
    return True

# ===== КОМАНДЫ =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот Блэкджек 🎰\n\n"
        "Формат: 1 на 1, без дилера, максимум 2 игрока в чате.\n\n"
        "Команды:\n"
        "/newgame – создать новую игру\n"
        "/join – присоединиться (до 2 игроков)\n"
        "/bet N – поставить N фишек перед игрой\n"
        "/startgame – начать игру, когда оба в игре\n"
        "/rematch – реванш теми же игроками\n"
        "/status – показать текущие карты\n"
        "/balance – твоё количество фишек\n"
        "/stats – твоя статистика\n"
        "/top – топ игроков по победам\n"
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
        "Создана новая игра!\n"
        "Игроки могут присоединиться командой /join.\n"
        "Затем поставьте ставки /bet и запустите /startgame."
    )

async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    game = games.get(chat_id)
    if not game:
        await update.message.reply_text("Сначала создайте игру командой /newgame.")
        return
    if game["started"]:
        await update.message.reply_text("Игра уже началась, присоединиться нельзя.")
        return
    if user_id in game["players"]:
        await update.message.reply_text("Ты уже в игре.")
        return
    if len(game["players"]) >= 2:
        await update.message.reply_text("В этой игре уже 2 игрока, мест нет.")
        return

    game["players"][user_id] = {
        "name": user.first_name,
        "hand": [],
        "stand": False,
        "busted": False,
        "bet": 0,
    }
    game["order"].append(user_id)

    ensure_stats(chat_id, user_id, user.first_name)
    ensure_balance(chat_id, user_id, user.first_name)
    bal = balances[chat_id][user_id]["balance"]

    await update.message.reply_text(
        f"{user.first_name} присоединился к игре!\n"
        f"Баланс: 💰 {bal} фишек.\n"
        "Сделай ставку /bet N (например, /bet 50)."
    )

async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    game = games.get(chat_id)
    if not game:
        await update.message.reply_text("Сначала создайте игру командой /newgame.")
        return
    if user_id not in game["players"]:
        await update.message.reply_text("Сначала присоединись к игре командой /join.")
        return
    if game["started"]:
        await update.message.reply_text("Игра уже началась, ставку сейчас менять нельзя.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /bet N\nНапример: /bet 50")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ставка должна быть числом.")
        return
    if amount <= 0:
        await update.message.reply_text("Ставка должна быть больше нуля.")
        return

    ensure_balance(chat_id, user_id, user.first_name)
    bal = balances[chat_id][user_id]["balance"]
    if amount > bal:
        await update.message.reply_text(f"У тебя нет столько фишек. Баланс: {bal}.")
        return

    game["players"][user_id]["bet"] = amount
    await update.message.reply_text(
        f"Ставка {amount} фишек установлена для {user.first_name}."
    )

async def cmd_startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game:
        await update.message.reply_text("Сначала создайте игру командой /newgame.")
        return
    if game["started"]:
        await update.message.reply_text("Игра уже идёт.")
        return
    if len(game["players"]) < 2:
        await update.message.reply_text("Нужно 2 игрока. Пусть второй сделает /join.")
        return

    # проверяем и списываем ставки, раздаём карты
    for uid, p in game["players"].items():
        ensure_balance(chat_id, uid, p["name"])
        bal = balances[chat_id][uid]["balance"]
        bet = p["bet"] or 10  # если не поставил /bet — ставка по умолчанию 10
        if bet > bal:
            await update.message.reply_text(
                f"{p['name']} не хватает фишек на ставку {bet}. Баланс: {bal}."
            )
            return

    for uid, p in game["players"].items():
        bet = p["bet"] or 10
        p["bet"] = bet
        balances[chat_id][uid]["balance"] -= bet
        p["hand"] = [draw_card(), draw_card()]
        p["stand"] = False
        p["busted"] = False

    game["started"] = True
    game["finished"] = False
    game["turn"] = 0

    await update.message.reply_text("Игра началась! Раздаю карты 👇")
    await show_turn(chat_id, context)

async def cmd_rematch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game:
        await update.message.reply_text("Ещё не было игры. Используйте /newgame.")
        return
    if not game["finished"]:
        await update.message.reply_text("Текущая игра ещё не окончена. Доиграйте или /cancel.")
        return
    if len(game["players"]) != 2:
        await update.message.reply_text("Для реванша нужно, чтобы играли 2 игрока.")
        return

    for uid, p in game["players"].items():
        p["hand"] = []
        p["stand"] = False
        p["busted"] = False
        # ставка остаётся прежней, можно изменить /bet перед /startgame

    game["started"] = False
    game["finished"] = False

    await update.message.reply_text(
        "Реванш! Игроки те же.\n"
        "Можете изменить ставки /bet и снова запустить /startgame."
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game or not game["started"]:
        await update.message.reply_text("Сейчас нет активной игры. /newgame чтобы создать.")
        return
    await update.message.reply_text(format_game_state(game))

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("Игра не найдена.")
        return
    del games[chat_id]
    await update.message.reply_text("Игра отменена.")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    ensure_balance(chat_id, user_id, user.first_name)
    bal = balances[chat_id][user_id]["balance"]
    await update.message.reply_text(f"Твой баланс в этом чате: 💰 {bal} фишек.")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    chat_stats = stats.get(chat_id, {})
    s = chat_stats.get(user_id)
    if not s:
        await update.message.reply_text("У тебя пока нет статистики в этом чате. Сыграй пару игр!")
        return
    await update.message.reply_text(
        f"Статистика {s['name']} в этом чате:\n"
        f"🏆 Победы: {s['wins']}\n"
        f"😔 Поражения: {s['losses']}\n"
        f"🤝 Ничьи: {s['draws']}\n"
        f"💥 Переборы: {s['busts']}"
    )

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_stats = stats.get(chat_id, {})
    if not chat_stats:
        await update.message.reply_text("В этом чате ещё нет игр. /newgame чтобы начать.")
        return
    players = list(chat_stats.values())
    players.sort(key=lambda x: x["wins"], reverse=True)
    lines = ["🏆 Топ игроков по победам:"]
    for i, p in enumerate(players[:10], start=1):
        lines.append(f"{i}. {p['name']} — {p['wins']} побед")
    await update.message.reply_text("\n".join(lines))

# ===== ЗАВЕРШЕНИЕ ИГРЫ =====

async def finish_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games[chat_id]
    results = []
    pot = 0
    for uid in game["order"]:
        p = game["players"][uid]
        s = score(p["hand"])
        busted = s > 21
        bet = p["bet"]
        pot += bet
        results.append((uid, p["name"], s, busted, bet))
        if busted:
            ensure_stats(chat_id, uid, p["name"])
            stats[chat_id][uid]["busts"] += 1

    alive = [r for r in results if not r[3]]
    state = format_game_state(game)
    balance_info = ""

    if len(alive) == 0:
        # оба перебор
        for uid, name, s, busted, bet in results:
            ensure_stats(chat_id, uid, name)
            stats[chat_id][uid]["losses"] += 1
        result_text = "Оба игрока с перебором 💥\nБанк сгорает, ставки не возвращаются."
        balance_info = "Баланс учитывает списанные ставки."
    elif len(alive) == 1:
        winner = alive[0]
        winner_id, winner_name, winner_score, _, _ = winner
        loser = [x for x in results if x[0] != winner_id][0]
        loser_id, loser_name, loser_score, _, _ = loser

        ensure_stats(chat_id, winner_id, winner_name)
        ensure_stats(chat_id, loser_id, loser_name)
        stats[chat_id][winner_id]["wins"] += 1
        stats[chat_id][loser_id]["losses"] += 1

        ensure_balance(chat_id, winner_id, winner_name)
        balances[chat_id][winner_id]["balance"] += pot

        result_text = (
            f"Победитель: {winner_name} с {winner_score} очками! 🎉\n"
            f"Проиграл: {loser_name} ({loser_score} очков)"
        )
        balance_info = (
            f"{winner_name} получает банк {pot} фишек.\n"
            f"Баланс {winner_name}: {balances[chat_id][winner_id]['balance']}\n"
            f"Баланс {loser_name}: {balances[chat_id][loser_id]['balance']}"
        )
    else:
        a, b = alive[0], alive[1]
        a_id, a_name, a_score, _, a_bet = a
        b_id, b_name, b_score, _, b_bet = b

        ensure_stats(chat_id, a_id, a_name)
        ensure_stats(chat_id, b_id, b_name)

        if a_score > b_score:
            winner_id, winner_name, winner_score = a_id, a_name, a_score
            loser_id, loser_name, loser_score = b_id, b_name, b_score
        elif b_score > a_score:
            winner_id, winner_name, winner_score = b_id, b_name, b_score
            loser_id, loser_name, loser_score = a_id, a_name, a_score
        else:
            # ничья
            stats[chat_id][a_id]["draws"] += 1
            stats[chat_id][b_id]["draws"] += 1
            ensure_balance(chat_id, a_id, a_name)
            ensure_balance(chat_id, b_id, b_name)
            balances[chat_id][a_id]["balance"] += a_bet
            balances[chat_id][b_id]["balance"] += b_bet
            result_text = (
                f"Ничья! {a_name} и {b_name} оба с {a_score} очками 🤝"
            )
            balance_info = (
                "Ставки возвращены игрокам.\n"
                f"Баланс {a_name}: {balances[chat_id][a_id]['balance']}\n"
                f"Баланс {b_name}: {balances[chat_id][b_id]['balance']}"
            )
            text = f"Игра окончена!\n\n{state}\n\n{result_text}\n\n{balance_info}"
            await context.bot.send_message(chat_id, text)
            game["started"] = False
            game["finished"] = True
            return

        ensure_balance(chat_id, winner_id, winner_name)
        balances[chat_id][winner_id]["balance"] += pot
        stats[chat_id][winner_id]["wins"] += 1
        stats[chat_id][loser_id]["losses"] += 1

        result_text = (
            f"Победитель: {winner_name} с {winner_score} очками! 🎉\n"
            f"Проиграл: {loser_name} ({loser_score} очков)"
        )
        balance_info = (
            f"{winner_name} получает банк {pot} фишек.\n"
            f"Баланс {winner_name}: {balances[chat_id][winner_id]['balance']}\n"
            f"Баланс {losер_name}: {balances[chat_id][loser_id]['balance']}"
        )

    text = f"Игра окончена!\n\n{state}\n\n{result_text}\n\n{balance_info}"
    await context.bot.send_message(chat_id, text)
    game["started"] = False
    game["finished"] = True

# ===== ОБРАБОТКА КНОПОК =====

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    game = games.get(chat_id)
    if not game:
        await query.edit_message_text("Игра уже закончена или не создана. /newgame чтобы начать новую.")
        return
    if not game["started"]:
        await query.edit_message_text("Игра ещё не началась. Напишите /startgame.")
        return
    if user_id not in game["players"]:
        await query.answer("Ты не участвуешь в этой игре.", show_alert=True)
        return

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
                f"{player['name']}: {' ".join(player['hand'])} = {s} (перебор 💥)\n\n"
                "Ход переходит к следующему игроку."
            )
            await query.edit_message_text(text)
        else:
            text = (
                f"{player['name']} взял карту: {player['hand'][-1]}\n"
                f"{player['name']}: {' ".join(player['hand'])} = {s}\n\n"
                "Жми Hit или Stand."
            )
            await query.edit_message_text(text, reply_markup=turn_keyboard())
            return
    elif query.data == "stand":
        player["stand"] = True
        text = (
            f"{player['name']} остановился.\n"
            f"{player['name']}: {' ".join(player['hand'])} = {score(player['hand'])}\n\n"
            "Ход переходит к следующему игроку."
        )
        await query.edit_message_text(text)

    if all_players_done(game):
        await finish_game(chat_id, context)
        return

    while True:
        game["turn"] = (game["turn"] + 1) % len(game["order"])
        next_id = game["order"][game["turn"]]
        next_p = game["players"][next_id]
        if not next_p["stand"] and not next_p["busted"]:
            break

    await show_turn(chat_id, context)

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("bet", cmd_bet))
    app.add_handler(CommandHandler("startgame", cmd_startgame))
    app.add_handler(CommandHandler("rematch", cmd_rematch))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()

if __name__ == "__main__":
    main()
