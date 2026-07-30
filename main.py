import asyncio
import logging
import os
import random
import traceback
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from config import TOKEN, MAX_COLLECTION_PER_USER, API_BASE
from database import Database
from politicians import politicians

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("politician_bot")

db = Database("politician_cards.db")

PAGE_SIZE = 8


def _image_path(politician_id: str, variant: str = "") -> str | None:
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        if variant:
            path = os.path.join("images", f"{politician_id}_{variant}.{ext}")
            if os.path.exists(path):
                return path
        path = os.path.join("images", f"{politician_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


async def give_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.text.startswith("/"):
        return

    text = update.message.text.strip().lower()
    if "мудак" not in text:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    cards = db.get_cards(user.id)
    if len(cards) >= MAX_COLLECTION_PER_USER:
        await update.message.reply_text(
            f"\u274c У тебя уже {MAX_COLLECTION_PER_USER} карт! Освободи место через /release."
        )
        return

    is_boss = politicians.boss and random.random() < 0.15

    if is_boss:
        politician = politicians.boss
        variant = "boss"
        influence = max(50, politician.influence + random.randint(-5, 5))
        charisma = max(50, politician.charisma + random.randint(-5, 5))
        stamina = max(50, politician.stamina + random.randint(-5, 5))
        power = max(50, politician.power + random.randint(-5, 5))
    else:
        politician = politicians.get_random()
        variant = ""
        if politician.id == "putin" and random.random() < 0.3:
            variant = "old"
        influence = max(10, politician.influence + random.randint(-10, 10))
        charisma = max(10, politician.charisma + random.randint(-10, 10))
        stamina = max(10, politician.stamina + random.randint(-10, 10))
        power = max(10, politician.power + random.randint(-10, 10))

    card_id, tag = db.add_card(
        user.id, politician.id, power,
        variant=variant,
        influence=influence,
        charisma=charisma,
        stamina=stamina,
    )

    boss_icon = "\U0001f451 " if is_boss else ""
    title_text = "\U0001f451 **БОСС** " if is_boss else "\U0001f539 "
    caption = (
        f"{boss_icon}**Новая карта!**\n\n"
        f"{title_text}**{politician.name}**\n"
        f"{politician.description}\n\n"
        f"\U0001f4cb `{tag}_{card_id}`\n"
        f"\U000026a1 Сила: **{power}**\n"
        f"\U0001f399 Влияние: **{influence}**\n"
        f"\U0001f4ac Харизма: **{charisma}**\n"
        f"\U0001f4aa Выносливость: **{stamina}**"
    )
    img_path = _image_path(politician.id, variant)
    if img_path:
        with open(img_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f44b Привет! Я бот с карточками политиков.\n\n"
        "\U0001f4a1 Напиши в чат \"Мудак\" — получишь случайную карту политика!\n\n"
        "\U0001f4cb **Команды:**\n"
        "/collection — мои карты\n"
        "/profile — моя статистика\n"
        "/politicians — список всех политиков\n"
        "/fav <id> — добавить/убрать из избранного\n"
        "/release <id> — удалить карту\n"
        "/stats — статистика бота",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = db.get_user_stats(user.id)

    if not stats:
        await update.message.reply_text("\U0001f4ca У тебя пока нет карт.")
        return

    lines = [
        f"\U0001f4e6 **Всего карт:** {stats.catch_count}",
        f"\U0001f465 **Уникальных:** {stats.unique_caught}/{len(politicians.all)}",
        f"\U000026a1 **Общая сила:** {stats.total_power}",
    ]
    await update.message.reply_text(
        f"\U0001f4ca **Профиль {user.full_name}**\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_politicians(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = []
    for p in politicians.all:
        cnt = db.get_card_count(update.effective_user.id, p.id)
        owned = f" ({cnt}\u0448\u0442)" if cnt > 0 else ""
        lines.append(f"\U0001f539 **{p.name}**{owned}")

    await update.message.reply_text(
        f"\U0001f4cd **Все политики ({len(politicians.all)} \u0448\u0442.)**\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global_stats = db.get_global_stats()

    top_text = ""
    for i, u in enumerate(global_stats["top_users"][:5], 1):
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, u["user_id"])
            name = user.user.full_name if user else f"ID:{u['user_id']}"
        except Exception:
            name = f"ID:{u['user_id']}"
        top_text += f"**{i}.** {name} — {u['catch_count']} \u0448\u0442\n"

    await update.message.reply_text(
        f"\U0001f4ca **Статистика бота**\n\n"
        f"\U0001f3c5 Всего поймано: **{global_stats['total_caught']}**\n"
        f"\U0001f465 Участников: **{global_stats['total_users']}**\n"
        f"\U0001f3f0 Политиков: **{len(politicians.all)}**\n\n"
        f"\U0001f3c6 **Топ-5:**\n{top_text}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_fav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("\u274c Укажи ID карты. Пример: /fav 5")
        return

    clean = args[0].lstrip("#")
    if not clean.isdigit():
        await update.message.reply_text("\u274c Укажи числовой ID.")
        return

    card_id = int(clean)
    cards = db.get_cards(update.effective_user.id)
    card = next((c for c in cards if c.id == card_id), None)
    if not card:
        await update.message.reply_text("\u274c Карта с таким ID не найдена.")
        return

    result = db.toggle_favorite(card_id, update.effective_user.id)
    status = "\u2b50 добавлена в избранное" if result else "\u2b50 убрана из избранного"
    p = politicians.get(card.politician_id)
    name = p.name if p else "?"
    await update.message.reply_text(f"\u2705 `{card.tag}_{card_id}` {name} {status}!")


async def cmd_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("\u274c Укажи ID карты. Пример: /release 5")
        return

    clean = args[0].lstrip("#")
    if not clean.isdigit():
        await update.message.reply_text("\u274c Укажи числовой ID.")
        return

    card_id = int(clean)
    cards = db.get_cards(update.effective_user.id)
    card = next((c for c in cards if c.id == card_id), None)
    if not card:
        await update.message.reply_text("\u274c Карта не найдена в твоей коллекции.")
        return

    p = politicians.get(card.politician_id)
    name = p.name if p else "?"
    db.remove_card(card_id, update.effective_user.id)
    await update.message.reply_text(f"\U0001f5d1\ufe0f Карта `{card.tag}_{card_id}` {name} удалена.")


async def cmd_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cards = db.get_cards(user.id)
    if not cards:
        await update.message.reply_text("\U0001f4ed У тебя пока нет карт. Угадывай политиков в чате!")
        return

    await _show_collection_page(update, context, cards, 0)


async def _show_collection_page(update: Update, context: ContextTypes.DEFAULT_TYPE, cards: list, page: int):
    total_pages = max(1, (len(cards) - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_cards = cards[start:end]

    lines = []
    for card in page_cards:
        p = politicians.get(card.politician_id)
        name = p.name if p else "?"
        fav = "\u2b50 " if card.is_favorite else ""
        lines.append(f"{fav}`{card.tag}_{card.id}` **{name}** (\U000026a1{card.power})")

    stats = db.get_user_stats(user_id=cards[0].user_id)
    header = (
        f"\U0001f4ed **Коллекция {update.effective_user.full_name}**\n"
        f"\U0001f4e6 Всего: **{stats.catch_count}** | Уникальных: **{stats.unique_caught}/{len(politicians.all)}**\n\n"
        if stats else ""
    )

    text = header + "\n".join(lines) if lines else header + "Пока пусто..."

    keyboard = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(f"\u25c0 {page}/{total_pages}", callback_data=f"col_page_{page - 1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(f"{page + 2}/{total_pages} \u25b6", callback_data=f"col_page_{page + 1}"))
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def collection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("col_page_"):
        page = int(data.split("_")[-1])
        cards = db.get_cards(update.effective_user.id)
        await _show_collection_page(update, context, cards, page)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Update {update} caused error {context.error}")


def main():
    if not TOKEN:
        log.error("Токен не настроен! Укажи TELEGRAM_TOKEN в переменных окружения Railway.")
        return

    async def set_commands(app: Application):
        await app.bot.set_my_commands([
            BotCommand("start", "Приветствие"),
            BotCommand("collection", "Мои карты"),
            BotCommand("profile", "Моя статистика"),
            BotCommand("politicians", "Список политиков"),
            BotCommand("fav", "Избранное (ID карты)"),
            BotCommand("release", "Удалить карту (ID)"),
            BotCommand("stats", "Статистика бота"),
        ])

    app = Application.builder().token(TOKEN).post_init(set_commands).base_url(API_BASE).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("collection", cmd_collection))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("politicians", cmd_politicians))
    app.add_handler(CommandHandler("fav", cmd_fav))
    app.add_handler(CommandHandler("release", cmd_release))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(collection_callback, pattern=r"^col_page_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, give_card))

    app.add_error_handler(error_handler)

    log.info("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
