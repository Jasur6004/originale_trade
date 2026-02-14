import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import config
from handlers import router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Настройка event loop для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    """Главная функция запуска бота"""
    # Проверка токена
    # Проверка токена
    if not config.BOT_TOKEN:
        logger.error("⚠️ BOT_TOKEN не найден! Установите переменную окружения BOT_TOKEN в настройках Railway.")
        return
    
    # Инициализация бота и диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутера
    dp.include_router(router)
    
    # Запуск бота
    # Запуск бота с автоматическим перезапуском при ошибках
    logger.info("🚀 Бот запущен на Railway!")
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в работе бота: {e}")
            logger.info("🔄 Перезапуск через 5 секунд...")
            await asyncio.sleep(5)
        finally:
            # Закрываем сессию только при полном выходе
            if bot.session:
                await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

