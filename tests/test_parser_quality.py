import unittest

import run_scraper
from tools import parser_quality


class ParserQualityTests(unittest.TestCase):
    def parse_table(self, table, page_text="Schedule of Remuneration and Expenses - Chief and Council"):
        quality = parser_quality.score_candidate_table(table, page_text)
        people = run_scraper._extract_people_from_keyword_table(table)
        result = parser_quality.validate_people(
            people,
            source_total=parser_quality.source_total_from_table(table),
            table_quality=quality,
        )
        return quality, result

    def test_clean_standard_table(self):
        table = [
            ["Name", "Position", "Number of Months", "Remuneration", "Travel", "Expenses", "Credit Card", "Total"],
            ["Scott Eashappie", "Chief", "12", "108,791", "13,000", "256,865", "264,662", "643,318"],
            ["Shawn Spencer", "Councillor", "12", "87,000", "13,000", "84,696", "-", "184,696"],
            ["Total", "", "", "195,791", "26,000", "341,561", "264,662", "828,014"],
        ]
        quality, result = self.parse_table(table)
        self.assertTrue(quality["accepted"])
        self.assertFalse(result["manual_review_required"])
        self.assertEqual(len(result["people"]), 2)
        self.assertEqual(result["people"][0]["role"], "Chief")
        self.assertEqual(result["people"][0]["travelExpenses"], 534527)

    def test_combined_travel_expense_header(self):
        table = [
            ["Chief and Council", "Name", "Number of Months", "Remuneration", "Travel and Per Diems", "Other Payments"],
            ["Chief", "Francis X Iron", "12", "90,000", "150,465", "126,605"],
            ["Councillor", "Lorne Iron", "12", "66,000", "116,067", "67,975"],
        ]
        quality, result = self.parse_table(table)
        self.assertTrue(quality["accepted"])
        self.assertFalse(result["manual_review_required"])
        self.assertEqual(result["people"][0]["travel"], 150465)
        self.assertEqual(result["people"][0]["otherPayments"], 126605)

    def test_other_remuneration_wording(self):
        table = [
            ["Name", "Role", "Months", "Salary", "Expense reimbursement", "Other remuneration", "Total paid"],
            ["Jane Bear", "Chief", "12", "80,000", "10,000", "5,000", "95,000"],
            ["John Bear", "Councillor", "12", "40,000", "2,000", "1,000", "43,000"],
        ]
        quality, result = self.parse_table(table)
        self.assertTrue(quality["accepted"])
        self.assertEqual(result["people"][0]["remuneration"], 80000)
        self.assertEqual(result["people"][0]["expenses"], 10000)
        self.assertEqual(result["people"][0]["otherPayments"], 5000)

    def test_missing_values_do_not_create_nan(self):
        table = [
            ["Name", "Position", "Months", "Remuneration", "Travel", "Other", "Total"],
            ["Mary Stone", "Chief", "12", "75,000", "", "", "75,000"],
            ["Tom Stone", "Councillor", "6", "20,000", "-", "", "20,000"],
        ]
        _, result = self.parse_table(table)
        self.assertFalse(result["manual_review_required"])
        self.assertEqual(result["people"][0]["travelExpenses"], 0)
        self.assertEqual(result["people"][0]["other"], 0)

    def test_footer_total_row_is_not_an_official(self):
        table = [
            ["Name", "Position", "Months", "Remuneration", "Expenses", "Total"],
            ["Alice Star", "Chief", "12", "70,000", "10,000", "80,000"],
            ["Total", "", "", "70,000", "10,000", "80,000"],
        ]
        _, result = self.parse_table(table)
        self.assertEqual([p["name"] for p in result["people"]], ["Alice Star"])

    def test_wrapped_name_cell(self):
        table = [
            ["Name", "Position", "Months", "Remuneration", "Travel", "Total"],
            ["Bellegarde,\nClarence", "Chief", "12", "90,497", "77,472", "167,969"],
            ["Bellegarde,\nHolly", "Councillor", "12", "49,227", "27,348", "76,575"],
        ]
        _, result = self.parse_table(table)
        self.assertEqual(result["people"][0]["name"], "Bellegarde, Clarence")
        self.assertEqual(len(result["people"]), 2)

    def test_different_header_wording(self):
        table = [
            ["Elected Official", "Title", "Served", "Honoraria", "Allowance", "Total Paid"],
            ["Sarah Lake", "Chief", "12", "88,000", "12,000", "100,000"],
            ["Peter Lake", "Council Member", "12", "44,000", "6,000", "50,000"],
        ]
        quality, result = self.parse_table(table, "Elected officials remuneration paid expenses reimbursed")
        self.assertTrue(quality["accepted"])
        self.assertFalse(result["manual_review_required"])
        self.assertEqual(result["people"][1]["role"], "Councillor")

    def test_unrelated_financial_statement_table_is_refused(self):
        table = [
            ["Program", "Revenue", "Expenses", "Surplus"],
            ["Housing project", "100,000", "90,000", "10,000"],
            ["Administration", "50,000", "45,000", "5,000"],
        ]
        quality = parser_quality.score_candidate_table(table, "Consolidated statement of operations")
        self.assertFalse(quality["accepted"])
        result = parser_quality.validate_people([], table_quality=quality)
        self.assertTrue(result["manual_review_required"])


if __name__ == "__main__":
    unittest.main()
