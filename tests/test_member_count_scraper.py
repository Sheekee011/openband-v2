import unittest

from tools.member_count_scraper import parse_population_page


class MemberCountScraperTests(unittest.TestCase):
    def test_parses_isc_registered_population(self):
        page = """
        <h1>Registered Population</h1>
        <dl><dt>Official Name</dt><dd>Muskoday First Nation</dd>
        <dt>Number</dt><dd>371</dd></dl>
        <p>Registered Population as of January, 2026</p>
        <table><tr><td>Total Registered Population</td><td>2,531</td></tr></table>
        """
        result = parse_population_page(page)
        self.assertEqual(result["registeredMembers"], 2531)
        self.assertEqual(result["sourcePeriod"], "January 2026")
        self.assertEqual(result["officialName"], "Muskoday First Nation")
        self.assertEqual(result["bandNumber"], 371)

    def test_refuses_page_without_total(self):
        with self.assertRaisesRegex(ValueError, "Total Registered Population"):
            parse_population_page("<h1>Registered Population</h1><p>Temporarily unavailable</p>")


if __name__ == "__main__":
    unittest.main()
