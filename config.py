# Конфигурационный файл бота
# Здесь вы можете легко изменить настройки
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла (если он существует)
load_dotenv()

# Партнерская ссылка для регистрации
PARTNER_LINK = os.getenv("PARTNER_LINK", "https://u3.shortink.io/smart/GV0dn1IA9up6Yr")

# Ваш Telegram юзернейм (без @)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Modex_adm")

# Секретный код доступа для активации бота
ACCESS_CODE = os.getenv("ACCESS_CODE", "modex8687")

# Токен бота от @BotFather (берется из переменной окружения для безопасности)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ключ API Groq для ИИ-ассистента (бесплатный и не требует оплаты)
# Получить ключ: https://console.groq.com/
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Настройки анализа
ANALYSIS_DELAY = 3  # Задержка перед показом результата (секунды)
CONFIDENCE_MIN = 82  # Минимальная уверенность в %
CONFIDENCE_MAX = 99  # Максимальная уверенность в %

# Строгость фильтрации сигналов (чем выше, тем меньше сигналов, но точнее)
# Рекомендуется: 0.85-0.95 для максимальной точности
SIGNAL_STRICTNESS = 0.65  # 65% - больше сигналов при нормальном качестве

# Минимальное количество индикаторов, которые должны подтверждать сигнал
MIN_INDICATORS_AGREEMENT = 3  # Из 10 возможных индикаторов

# Вероятность выигрыша для OTC пар (%)
OTC_WIN_PROBABILITY = 82

# --- Pocket Option API / WebSocket (реальные котировки и свечи) ---
# SSID: из браузера F12 → Network → WS → сообщение 42["auth",{...}] (полная строка).
# Регионы: api-eu / api-us-north / api-asia / demo-api-eu
USE_POCKET_OPTION_API = os.getenv("USE_POCKET_OPTION_API", "true").lower() in ("true", "1", "yes")
POCKET_OPTION_WS_URL = os.getenv(
    "POCKET_OPTION_WS_URL",
    "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket"
)
# Полный формат сессии из браузера (F12 → Network → WS → сообщение 42["auth",...])
POCKET_OPTION_SSID = os.getenv(
    "POCKET_OPTION_SSID",
    '42["auth",{"sessionToken":"95789b878b9d461fedf7207d489a9579","uid":"28308807","lang":"en","currentUrl":"cabinet/demo-quick-high-low","isChart":1}]'
)
POCKET_OPTION_IS_DEMO = os.getenv("POCKET_OPTION_IS_DEMO", "true").lower() in ("true", "1", "yes")

# Маппинг пар на символы активов Pocket Option (OTC для ликвидности)
POCKET_OPTION_ASSET_IDS = {
    "EUR/USD": "EURUSD_otc",
    "GBP/USD": "GBPUSD_otc",
    "USD/JPY": "USDJPY_otc",
    "USD/CHF": "USDCHF_otc",
    "USD/CAD": "USDCAD_otc",
    "AUD/USD": "AUDUSD_otc",
    "NZD/USD": "NZDUSD_otc",
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "XAU/USD": "XAUUSD_otc",
    "GOLD": "XAUUSD_otc",
    "SILVER": "XAGUSD_otc",
    "OIL": "UKBrent_otc",
    "SP500": "SP500_otc",
    "NASDAQ": "NASUSD_otc",
    "APPLE": "#AAPL_otc",
    "TESLA": "#TSLA_otc",
    "AMAZON": "#AMZN_otc",
    # Дополнительно под твои MAIN_PAIRS / OTC
    "AUD/CHF": "AUDCHF_otc",
    "CAD/CHF": "CADCHF_otc",
    "EUR/CHF": "EURCHF_otc",
    "GBP/AUD": "GBPAUD_otc",
    "GBP/CHF": "GBPCHF_otc",
    "EUR/JPY": "EURJPY_otc",
    "AUD/CAD": "AUDCAD_otc",
    "EUR/CAD": "EURCAD_otc",
    "GBP/CAD": "GBPCAD_otc",
    "AUD/JPY": "AUDJPY_otc",
}

# URL картинок для интерфейса (можно заменить на свои)
IMAGE_MAIN_MENU = "menu.jpg"  # Главное меню
IMAGE_SIGNAL_BUY = "up.jpg"  # Ваша картинка для сигнала ВВЕРХ
IMAGE_SIGNAL_SELL = "doun.jpg"  # Ваша картинка для сигнала ВНИЗ  # Сигнал ВНИЗ
IMAGE_TRAINING = "trade.jpg"    # Обучение
IMAGE_SUPPORT = "support.jpg"        # Поддержка
IMAGE_ASSISTENT = "ai.jpg"  #ИИ изооброжение
IMAGE_STATISTICS = "stat.jpg"  # Статистика

# Можно использовать локальные файлы (если есть)
# Для локальных файлов используйте: open("images/main_menu.jpg", "rb")
USE_LOCAL_IMAGES = True # Если True, будут использоваться локальные файлы из папки images/

# Список основных валютных пар
MAIN_PAIRS = [
    "AUD/CHF",
    "CAD/CHF",
    "EUR/CHF",
    "EUR/USD",
    "GBP/AUD",
    "GBP/CHF",
    "GBP/USD",
    "USD/CAD",
    "USD/CHF",
    "USD/JPY",
    "EUR/JPY",
    "AUD/CAD",
    "AUD/USD",
    "EUR/CAD",
    "GBP/CAD",
    "AUD/JPY"
]

# Список OTC пар (можно изменить)
OTC_PAIRS = [
    "AUD/CAD - OTC",
    "AUD/CHF - OTC",
    "AUD/NZD - OTC",
    "AUD/USD - OTC",
    "CAD/CHF - OTC",
    "CAD/JPY - OTC",
    "CHF/JPY - OTC",
    "EUR/CHF - OTC",
    "EUR/GBP - OTC",
    "EUR/NZD - OTC",
    "GBP/JPY - OTC",
    "EUR/RUB - OTC",
    "GBP/USD - OTC",
    "NZD/JPY - OTC",
    "NZD/USD - OTC",
    "USD/CLP - OTC",
    "USD/PKR - OTC",
    "USD/DZD - OTC",
    "USD/ARS - OTC",
    "USD/BRL - OTC",
    "USD/BDT - OTC",
    "YER/USD - OTC",
    "LBP/USD - OTC",
    "TND/USD - OTC",
    "NGN/USD - OTC",
    "EUR/HUF - OTC",
    "CHF/NOK - OTC",
    "QAR/CNY - OTC",
    "AED/CNY - OTC",
    "JOD/CNY - OTC",
    "ZAR/USD - OTC",
    "USD/VND - OTC",
    "USD/THB - OTC",
    "USD/INR - OTC",
    "USD/EGP - OTC",
    "USD/MXN - OTC",
    "USD/SGD - OTC"
]

