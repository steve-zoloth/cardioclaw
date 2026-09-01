# CardioClaw

Automated weekly nuclear cardiology audio briefing for Andrew, a blind retired cardiologist. Steve (nuclear cardiologist, developer) maintains it.

**This is a separate project from `~/Documents/voice_pubmed_bot/`.** Don't mix work on the two in one conversation — if a session drifts into the other project, say so and suggest picking it up in its own thread.

## Where things live
- This repo (`~/CardioClaw`) — development workspace, pushed to [github.com/steve-zoloth/cardioclaw](https://github.com/steve-zoloth/cardioclaw), `main` branch is production.
- Oracle Cloud VM at `157.151.155.75` — where it actually runs. `ssh -i ~/Downloads/ssh-key-2026-04-07-2.key opc@157.151.155.75`. `~/CardioClaw/` there too.
- Flask serves the RSS feed; restart with `sudo systemctl restart cardiology-flask` — but only needed after editing `serve.py`'s *code*, not after content changes (it reads `episodes.json` fresh per request).
- Cron: `0 8 * * 1` (server time is GMT, so this actually fires ~3-4am Eastern — known, intentionally left as-is).

## Non-negotiable design constraint
Every interaction must be completable by voice alone — Andrew is blind and uses Siri/Apple Podcasts. Before changing anything user-facing, ask: can he still do this hands-free?

## Before changing cardio_claw.py or serve.py
- Check `git log` first — a lot of iteration happened here already (episode structure, feed caching/seasons, truncation, full-text). Don't rediscover a fixed bug.
- Build non-trivial changes on an isolated branch, test against real Oracle data, merge to `main` only once verified.
- Back up the Oracle file before overwriting it (`cp cardio_claw.py cardio_claw_backup_$(date +%Y%m%d_%H%M%S).py` there).
- There's a real end user depending on this working — verify before deploying, don't just ship and see.

## Known platform limitations (not fixable in our code, don't re-litigate)
- Apple Podcasts' "Up Next" queue is global/cross-show since iOS 16 — risk if Andrew ever follows other podcasts.
- Siri's "next episode" sometimes resumes instead of advancing — inconsistent, no fix on our end.
- Most target journals (JACC, JAMA, Eur Heart J, JNM) are paywalled — PMC full text is only available for a fraction of findings most weeks, and "open access on the publisher's site" doesn't mean "in PMC."
