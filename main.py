import os
import asyncio
from dotenv import load_dotenv  # <-- Добавили импорт
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
import splunklib.client as client
import splunklib.results as results

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Превращаем строку с ID ("12345,67890") в список чисел [12345, 67890]
raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = [int(uid.strip()) for uid in raw_ids.split(",") if uid.strip()]

SPLUNK_HOST = os.getenv("SPLUNK_HOST")
SPLUNK_PORT = int(os.getenv("SPLUNK_PORT", 8089))
SPLUNK_USER = os.getenv("SPLUNK_USER")
SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD")
# ========================================================

# 2. ИНИЦИАЛИЗАЦИЯ БОТА (использует переменные, которые мы загрузили выше)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# 3. ФУНКЦИЯ ДЛЯ SPLUNK
def query_splunk(search_query: str):
    try:
        service = client.connect(
            host=SPLUNK_HOST,
            port=SPLUNK_PORT,
            username=SPLUNK_USER,
            password=SPLUNK_PASSWORD,
            verify=False
        )
        if not search_query.strip().startswith("search"):
            search_query = f"search {search_query}"
            
        kwargs_normsearch = {"exec_mode": "normal"}
        job = service.jobs.create(search_query, **kwargs_normsearch)
        
        while True:
            while not job.is_ready():
                pass
            if job["isDone"] == "1":
                break
            asyncio.sleep(0.5)
            
        rr = results.ResultsReader(job.results(count=5))
        output = []
        for result in rr:
            if isinstance(result, dict):
                output.append(result.get('_raw', str(result)))
                
        if not output:
            return "Результаты не найдены."
            
        return "\n\n".join(output)[:4000]
        
    except Exception as e:
        return f"Ошибка при выполнении запроса в Splunk: {str(e)}"

# 4. ОБРАБОТЧИКИ КОМАНД TELEGRAM
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    if message.from_user.id not in ALLOWED_USER_IDS:
        await message.answer("Доступ запрещен.")
        return
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}! Отправь мне команду /splunk <запрос>.")

@dp.message(Command("splunk"))
async def splunk_command_handler(message: Message) -> None:
    if message.from_user.id not in ALLOWED_USER_IDS:
        await message.answer("Доступ запрещен.")
        return
        
    search_query = message.text.replace("/splunk", "").strip()
    if not search_query:
        await message.answer("Пожалуйста, укажите поисковый запрос.")
        return
        
    status_msg = await message.answer("Выполняю запрос в Splunk... ⏳")
    
    loop = asyncio.get_running_loop()
    splunk_results = await loop.run_in_executor(None, query_splunk, search_query)
    
    await status_msg.delete()
    await message.answer(f"**Результаты поиска:**\n\n`{splunk_results}`", parse_mode="Markdown")

# 5. ЗАПУСК БОТА
async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
