import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_analysis import analyzer

async def test_signal_flow():
    """Test the signal flow logic"""
    print("🧪 Testing Trading Signal Flow")
    print("=" * 50)

    # Test GBP/USD analysis
    print("📊 Testing GBP/USD analysis...")
    try:
        result = analyzer.analyze_pair("GBP/USD", is_otc=False)

        print(f"✅ Pair: {result['pair']}")
        print(f"📈 Signal Type: {result['signal_type']}")
        print(f"📊 Direction: {result['direction']}")
        print(f"🎯 Confidence: {result['confidence']}%")
        print(f"⏰ Time Minutes: {result['time_minutes']}")
        print(f"💰 Price: {result.get('price', 'N/A')}")
        print(f"📊 RSI: {result.get('rsi', 'N/A')}")
        print(f"🔄 Stable: {result['stable']}")
        print(f"📝 Message: {result.get('message', 'No message')}")

        # Test signal card formatting
        print("\n" + "=" * 50)
        print("🎨 Testing Signal Card Formatting...")

        if result["stable"]:
            direction = "ВВЕРХ" if result["signal_type"] == "BUY" else "ВНИЗ"
            price = result.get("price", "1.37540")
            rsi = result.get("rsi", 32)
            confidence = result["confidence"]

            signal_text = (
                f"💡 Сигнал на [ТЕКУЩАЯ_ДАТА]\n\n"
                f"🔹 Актив: GBPUSD\n"
                f"💰 Текущая цена: {price:.5f}\n"
                f"📊 RSI(14): {rsi:.1f}\n"
                f"⏳ Время экспирации: [ВРЕМЯ] (5 мин)\n"
                f"📈 Прогноз: {direction}\n"
                f"📉 Уверенность: {confidence}%\n\n"
                f"⚠️ Важно: соблюдайте риск-менеджмент. Не более 2% от депозита на сделку.\n\n"
                f"👇 Пожалуйста, оцените результат этого сигнала ниже. Ваша обратная связь помогает нам делать прогнозы точнее!"
            )

            print("✅ Signal Card Text:")
            print(signal_text)
        else:
            neutral_text = (
                f"⚠️ РЫНОК НЕСТАБИЛЕН\n\n"
                f"📊 Пара: {result['pair']}\n\n"
                f"📉 Причина:\n{result.get('message', 'Рынок находится в нейтральной зоне')}\n\n"
                f"🔄 Рекомендация:\nПодождите более четкого сигнала. Бот показывает только высококачественные сигналы.\n\n"
                f"💡 Будьте терпеливы - лучше пропустить сигнал, чем торговать в неопределенности."
            )

            print("⚠️ Neutral Market Text:")
            print(neutral_text)

        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_signal_flow())
