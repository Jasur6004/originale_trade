import asyncio

async def test_progress_bar():
    """Test the progress bar stages"""
    print("🧪 Testing Progress Bar Stages")
    print("=" * 50)

    # Стадии прогресса (общее время 10-12 секунд)
    stages = [
        ("Ищу лучший сигнал для тебя... ⚪️", 1.5),
        ("Анализирую рынок... 🟡", 1.5),
        ("Получаю данные по GBPUSD... 🔵", 1.5),
        ("Анализ завершен на 9%... Осталось 11 сек", 1.2),
        ("Анализ завершен на 18%... Осталось 10 сек", 1.2),
        ("Анализ завершен на 27%... Осталось 9 сек", 1.2),
        ("Анализ завершен на 36%... Осталось 8 сек", 1.2),
        ("Анализ завершен на 45%... Осталось 7 сек", 1.2),
        ("Анализ завершен на 54%... Осталось 6 сек", 1.2),
        ("Анализ завершен на 63%... Осталось 5 сек", 1.2),
        ("Анализ завершен на 72%... Осталось 4 сек", 1.2),
        ("Анализ завершен на 81%... Осталось 3 сек", 1.2),
        ("Анализ завершен на 90%... Осталось 2 сек", 1.2),
        ("Анализ завершен на 100%... Подготовка результата... ✅", 1.0),
    ]

    total_time = sum(delay for _, delay in stages)
    print(f"📊 Total progress bar time: {total_time} seconds")
    print("🎬 Simulating progress bar:")

    for i, (text, delay) in enumerate(stages, 1):
        print(f"[{i:2d}] {text} (delay: {delay}s)")
        await asyncio.sleep(delay)

    print("\n✅ Progress bar simulation completed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_progress_bar())
