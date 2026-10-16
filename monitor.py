"""Public GET checks. GitHub issue transitions use only this repo's ephemeral token."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import time
import urllib.request
from unittest.mock import patch

REPO = 'somchaisingh/globriq-website-monitor'
ROOT = Path(__file__).resolve().parent

def decide(active, first, second):
    if active and not first and not second:
        return 'recovery'
    first_keys = {(x['url'], x['kind']) for x in first}
    second_keys = {(x['url'], x['kind']) for x in second}
    if not active and first_keys & second_keys:
        return 'incident'
    return None

def stale(now, heartbeat):
    return heartbeat is None or heartbeat > now + 60 or now - heartbeat > 2700

def api(method, suffix, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + suffix,
        data=data, method=method, headers={
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

def opened(channel):
    # Only repository writers can apply these labels. Ignore untrusted issue bodies.
    return [x for x in api('GET', '/issues?state=open&per_page=100&labels=monitor-' + channel)
            if not x.get('pull_request') and x['user']['login'] == 'github-actions[bot]']

def notify(channel, failed, details):
    issues = opened(channel)
    link = 'https://github.com/' + REPO + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
    if failed and not issues:
        api('POST', '/issues', {'title': '[INCIDENT] ' + channel,
            'labels': ['monitor-' + channel],
            'body': '@somchaisingh\n\nConfirmed monitoring event. ' + details +
                    '\n\n[Monitor run](' + link + ')\n\nOne notification per incident; recovery is sent on this thread.'})
        print('incident:', channel)
    elif not failed and issues:
        for issue in issues:
            number = str(issue['number'])
            comments = api('GET', '/issues/' + number + '/comments?per_page=100')
            if not any('<!-- monitor-recovery -->' in x['body'] and
                       x['user']['login'] == 'github-actions[bot]' for x in comments):
                api('POST', '/issues/' + number + '/comments', {
                    'body': '<!-- monitor-recovery -->\n@somchaisingh **RECOVERED**: ' + channel +
                            '\n\n' + details + '\n\n[Monitor run](' + link + ')'})
            api('PATCH', '/issues/' + number, {'state': 'closed', 'state_reason': 'completed'})
        print('recovery:', channel)
    else:
        print('unchanged:', channel)

def probe(opener=None):
    output = StringIO()
    source = (ROOT / 'probe.py').read_text()
    def execute():
        try:
            exec(compile(source, 'probe.py', 'exec'), {})
        except SystemExit as e:
            if e.code not in (0, 1):
                raise RuntimeError('Unexpected probe exit')
    with redirect_stdout(output):
        if opener is None:
            execute()
        else:
            with patch('urllib.request.build_opener', return_value=opener):
                execute()
    result = json.loads(output.getvalue())
    if result.get('checks') != 7 or not result.get('readOnly') or not isinstance(result.get('failures'), list):
        raise RuntimeError('Incomplete probe result')
    return result['failures']

def observe(first, second, channel):
    event = decide(bool(opened(channel)), first, second)
    if event:
        notify(channel, event == 'incident',
            json.dumps({'first': first, 'confirmation': second}, separators=(',', ':')))
    print(json.dumps({'channel': channel, 'event': event, 'first': first, 'confirmation': second}))

def run(mode):
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise RuntimeError('Only the approved repository default branch can notify')
    if mode == 'watchdog':
        state = api('GET', '/issues/1')
        heartbeat = json.loads(state['body']).get('last_run')
        unhealthy = stale(time.time(), heartbeat)
        notify('scheduler', unhealthy,
               'No completed monitor heartbeat for more than 45 minutes; or its clock/state is invalid.'
               if unhealthy else 'Observer heartbeat is current again.')
        return
    if mode.startswith('fixture-'):
        if mode in ('fixture-monitor-failure', 'fixture-monitor-recovery'):
            notify('fixture-monitor', mode == 'fixture-monitor-failure',
                   'CONTROLLED FIXTURE: monitor execution failure/recovery. No production request.')
        else:
            from fixture import samples
            first, second = samples(mode == 'fixture-503')
            observe(first, second, 'fixture-availability')
        return
    try:
        first = probe()
        time.sleep(20)
        second = probe()
        observe(first, second, 'availability')
        notify('execution', False, 'Monitor execution and complete probes resumed.')
    except Exception as e:
        # Never send raw exceptions, upstream bodies, request data, or credentials.
        notify('execution', True, 'Monitor execution failed: ' + type(e).__name__)
    # Heartbeat indicates completed runner execution; HTTP health is a separate incident.
    api('PATCH', '/issues/1', {'body': json.dumps({'last_run': time.time()})})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['check', 'watchdog', 'fixture-503', 'fixture-healthy',
        'fixture-monitor-failure', 'fixture-monitor-recovery'], default='check')
    run(parser.parse_args().mode)
