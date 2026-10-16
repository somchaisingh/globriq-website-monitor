"""Transition tests: removing confirmation/dedup/recovery must break these."""
import unittest
from unittest.mock import patch
import json
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

    def test_execution_failure_lifecycle_uses_sanitized_deduplicated_notifications(self):
        # Only the external GitHub API is replaced; run/observe/notify stay real.
        issues = []
        comments = []
        heartbeat = {}
        def external_api(method, suffix, body=None):
            if method == 'GET' and suffix.startswith('/issues?'):
                label = suffix.split('labels=')[1]
                return [x for x in issues if x['state'] == 'open' and label in x['labels']]
            if method == 'POST' and suffix == '/issues':
                issue = dict(body, number=2, state='open', user={'login': 'github-actions[bot]'})
                issues.append(issue)
                return issue
            if suffix == '/issues/2/comments?per_page=100': return comments
            if method == 'POST' and suffix == '/issues/2/comments':
                comments.append(dict(body, user={'login': 'github-actions[bot]'}))
                return comments[-1]
            if method == 'PATCH' and suffix == '/issues/2':
                issues[0].update(body)
                return issues[0]
            if method == 'PATCH' and suffix == '/issues/1':
                heartbeat.update(json.loads(body['body']))
                return {'body': body['body']}
            raise AssertionError((method, suffix))
        env = {'GITHUB_REPOSITORY': monitor.REPO, 'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ID': '1'}
        with patch.dict('os.environ', env), patch('monitor.api', side_effect=external_api):
            with patch('urllib.request.build_opener', side_effect=RuntimeError('SECRET_MUST_NOT_BE_SENT')):
                monitor.run('check')
                monitor.run('check')
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]['labels'], ['monitor-execution'])
            self.assertIn('RuntimeError', issues[0]['body'])
            self.assertNotIn('SECRET_MUST_NOT_BE_SENT', issues[0]['body'])
            self.assertGreater(heartbeat['last_run'], 0)
            with patch('monitor.probe', return_value=[]), patch('time.sleep'):
                monitor.run('check')
                monitor.run('check')
            self.assertEqual(issues[0]['state'], 'closed')
            self.assertEqual(len(comments), 1)
            self.assertIn('RECOVERED', comments[0]['body'])

if __name__ == '__main__':
    unittest.main()
