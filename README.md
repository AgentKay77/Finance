# Finance Hub

Self-hosted personal finance hub PWA for Raspberry Pi 5. Modules are built in
phases; Phase 1 (this commit) ships the foundation: app factory, auth, base
templates, and an installable PWA shell.

## Phases

1. **Foundation (this PR).** Flask + SQLAlchemy + Alembic, Flask-Login auth,
   PWA manifest + service worker, Gunicorn + systemd + Caddy configs.
2. **Loan tracker.** Amortization, drift detection, snowball/avalanche.
3. **Net worth dashboard.** Assets + monthly snapshots.
4. **Bill calendar.** Recurring bills, monthly cashflow.
5. **Payoff what-if.** Scenarios on top of the amortization service.
6. **Goals + subscriptions.**

## Local development (Windows desktop or Pi)

```bash
python -m venv .venv
source .venv/bin/activate     # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

cp .env.example .env
# edit .env, in particular SECRET_KEY

flask --app wsgi:app db upgrade
flask --app wsgi:app run --debug
```

Then visit http://127.0.0.1:5000/ and register an account.

### Seed a demo user

```bash
python -m scripts.seed_demo
```

Creates `demo@finance.local` / `demo-password-123`.

## Running tests

```bash
pytest -q
ruff check .
black --check .
```

## Deploying to the Raspberry Pi

The `finance-hub.service` unit assumes `/home/pi/finance-hub` with a `.venv`
at `/home/pi/finance-hub/.venv`. Adjust paths if you use a different user.

```bash
# On the Pi (one-time):
sudo apt install python3-venv sqlite3 caddy
sudo loginctl enable-linger pi
git clone <this repo> /home/pi/finance-hub
cd /home/pi/finance-hub
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env && nano .env       # set SECRET_KEY, ALLOW_REGISTRATION

.venv/bin/flask --app wsgi:app db upgrade

sudo cp finance-hub.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now finance-hub

sudo cp Caddyfile /etc/caddy/Caddyfile     # edit hostname first
sudo systemctl reload caddy
```

Then on a phone or laptop on the same LAN, browse to `https://finance.lan`
(or whatever hostname you configured), sign in, and use **Add to Home Screen**
in iOS Safari to install the PWA.

### Daily backup

Add to `crontab -e`:

```
0 3 * * * /home/pi/finance-hub/scripts/backup_db.sh >> /var/log/finance-backup.log 2>&1
```

Set `BACKUP_RSYNC_TARGET` in `.env` (e.g. `user@nas:/volume1/backups/finance-hub`)
to push snapshots off-box.

## Phase 1 acceptance checklist (test these on the Pi)

- [ ] `systemctl status finance-hub` is active.
- [ ] `https://finance.lan/healthz` returns `ok`.
- [ ] You can register a user and sign in.
- [ ] Sign out works and session is cleared.
- [ ] Visiting from iOS Safari shows the **Add to Home Screen** option.
- [ ] After install, the app launches standalone (no Safari chrome) with the
      dark theme and rounded icon.
- [ ] In airplane mode, navigating back to a previously visited page shows the
      cached shell instead of a Safari error page.
- [ ] `journalctl -u finance-hub -f` shows access logs but **no balance
      amounts** (no balances exist yet, but the logging policy is in place).
- [ ] `scripts/backup_db.sh` produces a timestamped `.db.gz` in `./backups/`.

When all of the above pass, we move to **Phase 2 — Loan tracker**, starting
with a model + amortization signature review for your sign-off.

## Project layout

See the project plan in the original spec. Module folders are pre-created so
each later phase is an additive PR rather than a structural change.
