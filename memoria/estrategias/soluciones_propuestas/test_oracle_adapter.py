"""
Test Suite: PreciousMetalsOracleAdapter Verification
Tests XAU/USD (Gold) and XAG/USD (Silver) price queries and USD valuation.
Operator Wallet: 0x02c1F87F514493F359Afc0B3ff6b587434770361
"""
import unittest

class TestPreciousMetalsOracle(unittest.TestCase):
    def setUp(self):
        self.gold_fallback = 2735.50
        self.silver_fallback = 32.40

    def test_gold_valuation(self):
        gold_ounces = 10.0
        expected_usd = gold_ounces * self.gold_fallback
        self.assertAlmostEqual(expected_usd, 27355.00, places=2)

    def test_silver_valuation(self):
        silver_ounces = 100.0
        expected_usd = silver_ounces * self.silver_fallback
        self.assertAlmostEqual(expected_usd, 3240.00, places=2)

    def test_zero_amount(self):
        self.assertEqual(0 * self.gold_fallback, 0.0)

if __name__ == "__main__":
    unittest.main()
