from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден токен бота. Создайте файл .env и добавьте в него BOT_TOKEN=ваш_токен") 