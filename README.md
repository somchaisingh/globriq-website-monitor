# Globriq website public monitoring

Independent, public-URL-only observer. This repository contains no website application source, production credentials, deployment identities, or customer data. It has no Vercel project or production deployment integration.

The observer runs on free standard GitHub public-repository runners at minutes **07, 22, 37, 52 each hour**. It executes the previously qualified seven-request GET probe twice, **20 seconds apart**. Each request has a **10-second socket timeout** and redirects are refused. Matching URL/failure-kind failures in both samples open one incident. Two wholly healthy samples close it with one recovery comment. Open incidents are deduplicated across runs with labeled GitHub issues; unchanged healthy or unhealthy states send no comments.

| Public URL | Expected status / additional check |
| --- | --- |
| `https://www.globriq.com/` | 200; security/indexing headers and Contact form markup |
| `https://www.globriq.com/pricing` | 200; security/indexing headers |
| `https://www.globriq.com/api/contact` | GET 405; never POST |
| `https://globriq.com/` | 308 to canonical homepage |
| `https://globriq-website.vercel.app/` | 200 |
| `https://globriq-website-globriq.vercel.app/` | 302 to Vercel SSO |
| `https://globriq-website-git-main-globriq.vercel.app/` | 302 to Vercel SSO |

The hourly watchdog runs at minute **47** and opens a scheduler incident when the observer heartbeat is more than **45 minutes old**, missing, or implausibly in the future. Its recovery is sent on its next healthy heartbeat evaluation. The observer also reports caught execution errors and their recovery. Unexpected runner/API/job failures use GitHub's existing failed-workflow notification route. A monthly keepalive at **03:27 UTC on day 1** commits a timestamp only in this monitor repository to avoid the public-repository inactivity cutoff.

Incident issues and recovery comments mention only the configured owner, `@somchaisingh`. Delivery uses that owner's existing GitHub email notification settings. No email service, paid add-on, SMTP key, personal access token, or production token is installed. The observer/watchdog ephemeral `GITHUB_TOKEN` can read this repository and write its issues only; the monthly keepalive alone can write this monitor repository's contents. Workflows accept no PR or push events and run only from this exact repository's `main` branch.

Disable all three workflows in Actions, or run:

```sh
gh workflow disable monitor.yml --repo somchaisingh/globriq-website-monitor
gh workflow disable watchdog.yml --repo somchaisingh/globriq-website-monitor
gh workflow disable keepalive.yml --repo somchaisingh/globriq-website-monitor
```

Re-enable all three with `gh workflow enable` and run `monitor.yml` once with `mode=check`, followed by `watchdog.yml`. Do not delete state issue #1 or relabel incident issues. Closing a real active incident manually can cause a new alert on the next confirmed failed check.

Tests: `python3 -m unittest discover -v`, `python3 verify-prepared-workflow.py` (the original 11 offline checks), and `python3 fixture.py` (actual loopback healthy/503 responses; zero production requests). Manual fixture workflow modes use isolated fixture labels and never change public website responses.

Limitations:

- GitHub schedules can be late or dropped. This is sampled detection, with no uptime or notification-delivery SLA. A brief outage between samples can be missed. The watchdog shares GitHub with the observer and cannot independently detect a complete GitHub scheduling/notification outage. Repository disablement, simultaneous workflow disablement, account suspension, and loss of Gmail delivery can be silent.
- Public-repository schedules may be disabled after 60 days of repository inactivity if the monthly keepalive fails. Periodic delivery checks remain an operational responsibility; this observer cannot notify after all its schedules stop.
- The timeout is a socket-operation timeout, not a strict total request deadline. The workflow's five-minute timeout bounds an entire stuck observation; the watchdog checks for missed heartbeats.
- HTTP checks detect unexpected statuses (including 5xx), timeout/DNS/TLS errors and the listed contract changes from one runner region. They do not establish exact Vercel deployment SHA/alias mappings, detect a healthy-looking unauthorized replacement, or monitor all visitor requests and runtime errors.
- Browser JavaScript, Pricing calculations, Contact submissions/delivery, CAPTCHA acceptance, database/integration health, global availability, security advisories and CI are outside this monitor. Accepted CI failures do not feed these workflows.
- If GitHub issue/API writes fail, durable deduplication and issue-based delivery cannot work; native failed-workflow emails may recur until the platform recovers. Gmail receipt of future alerts cannot be proven by a past fixture.
- Standard public GitHub runners are free under current provider terms. This configuration does not enable larger runners, artifact/cache storage, a paid plan, or any other paid resource. Monitor future provider policy changes separately.

Provider references: [GitHub runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
