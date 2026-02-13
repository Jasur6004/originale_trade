import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_analysis import analyzer

async def test_error_handling():
    """Test error handling scenarios"""
    print("🧪 Testing Error Handling Scenarios")
    print("=" * 50)

    # Test with invalid pair
    print("📊 Testing invalid pair...")
    try:
        result = analyzer.analyze_pair("INVALID_PAIR", is_otc=False)
        print(f"✅ Invalid pair result: stable={result['stable']}, message='{result.get('message', 'No message')}'")
    except Exception as e:
        print(f"❌ Error with invalid pair: {e}")

    # Test OTC pair
    print("\n📊 Testing OTC pair...")
    try:
        result = analyzer.analyze_pair("EUR/USD - OTC", is_otc=True)
        print(f"✅ OTC pair result: stable={result['stable']}, direction={result.get('direction', 'N/A')}")
    except Exception as e:
        print(f"❌ Error with OTC pair: {e}")

    # Test neutral market scenario (force by modifying analyzer temporarily)
    print("\n📊 Testing neutral market scenario...")
    try:
        # Temporarily modify the analyzer to force neutral result
        original_strictness = analyzer._TradingAnalyzer__class__.SIGNAL_STRICTNESS
        analyzer._TradingAnalyzer__class__.SIGNAL_STRICTNESS = 0.99  # Very strict

        result = analyzer.analyze_pair("GBP/USD", is_otc=False)
        print(f"✅ Neutral market result: stable={result['stable']}, message='{result.get('message', 'No message')}'")

        # Restore original value
        analyzer._TradingAnalyzer__class__.SIGNAL_STRICTNESS = original_strictness

    except Exception as e:
        print(f"❌ Error with neutral market test: {e}")

    print("\n" + "=" * 50)
    print("✅ Error handling tests completed!")

if __name__ == "__main__":
    asyncio.run(test_error_handling())
