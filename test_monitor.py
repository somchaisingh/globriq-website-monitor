"""Transition tests: removing confirmation/dedup/recovery must break these."""
import unittest
import monitor

BAD = {'url': 'https://www.globriq.com/pricing', 'kind': 'status', 'status': 503}
OTHER = {'url': 'https://www.globriq.com/', 'kind': 'unavailable-or-timeout'}

class Transitions(unittest.TestCase):
    def test_healthy_is_quiet(self):
        self.assertEqual(monitor.decide(False, [], []), None)

    def test_one_failure_is_not_an_incident(self):
        self.assertEqual(monitor.decide(False, [BAD], []), None)

    def test_same_url_and_kind_requires_two_failed_samples(self):
        self.assertEqual(monitor.decide(False, [BAD], [OTHER]), None)
        self.assertEqual(monitor.decide(False, [BAD], [BAD]), 'incident')

    def test_open_incident_does_not_repeat(self):
        self.assertEqual(monitor.decide(True, [BAD], [BAD]), None)

    def test_recovery_requires_two_healthy_samples(self):
        self.assertEqual(monitor.decide(True, [BAD], []), None)
        self.assertEqual(monitor.decide(True, [], [BAD]), None)
        self.assertEqual(monitor.decide(True, [], []), 'recovery')

    def test_watchdog_threshold_and_clock_validation(self):
        self.assertFalse(monitor.stale(10000, 7400))
        self.assertTrue(monitor.stale(10000, 7200))
        self.assertTrue(monitor.stale(10000, 11000))
        self.assertTrue(monitor.stale(10000, None))

if __name__ == '__main__':
    unittest.main()
