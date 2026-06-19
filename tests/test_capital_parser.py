import unittest

from tools import capital_parser


class CapitalParserTests(unittest.TestCase):
    def test_budget_actual_prior_year_layout(self):
        pages = [
            """
            Example First Nation
            Consolidated Statement of Operations
            For the year ended March 31, 2025
            Schedules 2025 2025 2024
            Budget Actual Actual
            Revenue
            Indigenous Services Canada (Note 4) 1,000,000 2,000,000 1,800,000
            Rental income - 100,000 90,000
            Settlement 500,000 - 250,000
            Total revenue 1,500,000 2,100,000 2,140,000
            Program expenses
            Education 3 400,000 500,000 450,000
            Health 4 300,000 350,000 325,000
            Administration 5 600,000 700,000 650,000
            Total expenses 1,300,000 1,550,000 1,425,000
            Annual surplus 200,000 550,000 715,000
            """,
            """
            Example First Nation
            Consolidated Statement of Financial Position
            As at March 31, 2025
            2025 2024
            Cash resources 800,000 700,000
            Marketable securities 200,000 150,000
            Short-term debt - 25,000
            Current portion of long-term debt 50,000 45,000
            Long-term debt 450,000 475,000
            Tangible capital assets (Note 12) 4,000,000 3,500,000
            """,
            """
            Example First Nation
            Consolidated Statement of Changes in Net Financial Assets
            For the year ended March 31, 2025
            2025 2025 2024
            Budget Actual Actual
            Purchases of tangible capital assets - (600,000) (500,000)
            """,
        ]

        result = capital_parser.parse_page_texts(pages)

        self.assertEqual(result["parseStatus"], "parsed")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["totalRevenue"], 2100000)
        self.assertEqual(result["totalExpenses"], 1550000)
        self.assertEqual(result["annualSurplusDeficit"], 550000)
        self.assertEqual(result["cashInvestments"], 1000000)
        self.assertEqual(result["capitalSpending"]["total"], 600000)
        self.assertEqual(result["capitalAssets"], 4000000)
        self.assertEqual(result["debt"]["total"], 500000)

    def test_two_column_layout_and_negative_values(self):
        pages = [
            """
            Example First Nation
            Statement of Operations
            2024 2023
            Revenue
            Government transfer 900,000 850,000
            Investment income 100,000 80,000
            Expenses
            Education 600,000 550,000
            Operations 450,000 400,000
            Surplus (deficit) (50,000) (20,000)
            """,
            """
            Example First Nation
            Statement of Financial Position
            2024 2023
            Cash 75,000 60,000
            Long-term debt 300,000 350,000
            Tangible capital assets 2,000,000 1,800,000
            """,
            """
            Example First Nation
            Statement of Change in Net Debt
            2024 2023
            Acquisition of tangible capital assets (250,000) (200,000)
            """,
        ]

        result = capital_parser.parse_page_texts(pages)

        self.assertEqual(result["parseStatus"], "parsed")
        self.assertEqual(result["totalRevenue"], 1000000)
        self.assertEqual(result["totalExpenses"], 1050000)
        self.assertEqual(result["annualSurplusDeficit"], -50000)

    def test_unreconciled_categories_require_manual_review(self):
        summary = {
            "totalRevenue": 1000000,
            "totalExpenses": 500000,
            "annualSurplusDeficit": 500000,
            "revenueBreakdown": [{"category": "Other", "amount": 100000}],
            "expenseBreakdown": [
                {"category": "Education", "amount": 250000},
                {"category": "Health", "amount": 250000},
            ],
            "capitalSpending": None,
            "debt": None,
        }

        validation = capital_parser.validate_summary(summary)

        self.assertEqual(validation["parseStatus"], "manual_review")
        self.assertFalse(validation["publishable"])
        self.assertIn(
            "Revenue categories do not reconcile to total revenue",
            validation["warnings"],
        )

    def test_land_claims_are_not_classified_as_economic_development(self):
        self.assertEqual(
            capital_parser.broad_expense_category("Land Claims"),
            "Operations",
        )
        self.assertEqual(
            capital_parser.broad_expense_category("Land Management"),
            "Economic development",
        )


if __name__ == "__main__":
    unittest.main()
