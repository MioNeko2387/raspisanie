from playwright.sync_api import sync_playwright
import asyncio
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import threading
import time

TOKEN = "yourtoken"

DATABASE_FILE = "schedule_db.json"


def format_schedule(text):
    days = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье"
    ]

    result = []

    for day in days:
        if day not in text:
            continue

        start = text.find(day)

        next_positions = [
            text.find(next_day, start + 1)
            for next_day in days
            if text.find(next_day, start + 1) != -1
        ]

        end = min(next_positions) if next_positions else len(text)

        block = text[start:end].strip()

        result.append(f"\n📚 {block}\n")


    return "\n".join(result)


def get_monday(offset_weeks=0):
    today = datetime.today()

    monday = today - timedelta(days=today.weekday())
    monday += timedelta(weeks=offset_weeks)

    return monday.strftime("%d.%m.%Y")


def get_schedule(week_text=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        page.goto(
            "http://rsp.iseu.by/Raspisanie/TimeTable/umu.aspx"
        )

        page.wait_for_load_state("networkidle")

        # Выбор курса
        page.locator("a").filter(has_text="курс").click()
        page.locator("#ddlCourse_chosen").get_by_text("2 курс").click()

        page.wait_for_load_state("networkidle")

        # Выбор группы
        page.locator("a").filter(has_text="А41ИТ").click()
        page.locator("#ddlGroup_chosen").get_by_text("А41ТТ").click()

        page.wait_for_load_state("networkidle")

        # Если неделя указана — выбираем её
        if week_text:
            page.locator("#ddlWeek_chosen").click()
            page.locator("#ddlWeek_chosen").get_by_text(week_text).click()

            page.wait_for_load_state("networkidle")

        # Нажать показать
        page.locator("a").filter(has_text="Показать").click()

        # Ждём загрузку расписания
        page.wait_for_load_state("networkidle")

        # Получаем текст страницы
        raw_text = page.locator("body").inner_text()

        browser.close()

        return format_schedule(raw_text)


def update_database():
    current_week = get_schedule()

    next_week_date = get_monday(1)
    next_week = get_schedule(next_week_date)

    next_next_week_date = get_monday(2)
    next_next_week = get_schedule(next_next_week_date)

    data = {
        "week": current_week,
        "nweek": next_week,
        "nnweek": next_next_week
    }

    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_database():
    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {
            "week": "База данных пустая. Используй /update",
            "nweek": "База данных пустая. Используй /update",
            "nnweek": "База данных пустая. Используй /update"
        }


def auto_update_loop():
    while True:
        now = datetime.now()

        # Следующая полночь
        next_midnight = datetime.combine(
            now.date() + timedelta(days=1),
            datetime.min.time()
        )

        seconds_until_midnight = (
            next_midnight - now
        ).total_seconds()

        time.sleep(seconds_until_midnight)

        try:
            print("Автообновление базы расписания...")
            update_database()
            print("База расписания автоматически обновлена")

        except Exception as e:
            print(f"Ошибка автообновления: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот расписания работает.\n\nКоманды:\n/week\n/nweek\n/nnweek\n/update"
    )



async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_database()

    await update.message.reply_text(data["week"])


async def nweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_database()

    await update.message.reply_text(data["nweek"])


async def nnweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_database()

    await update.message.reply_text(data["nnweek"])


async def update_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Обновляю базу расписания...")

    try:
        await asyncio.to_thread(update_database)

        await update.message.reply_text(
            "✅ База расписания обновлена"
        )

    except Exception as e:
        await update.message.reply_text(f"Ошибка обновления: {e}")



# Фоновый поток автообновления
threading.Thread(
    target=auto_update_loop,
    daemon=True
).start()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("week", week))
app.add_handler(CommandHandler("nweek", nweek))
app.add_handler(CommandHandler("nnweek", nnweek))
app.add_handler(CommandHandler("update", update_db))

print("Бот запущен")

app.run_polling()