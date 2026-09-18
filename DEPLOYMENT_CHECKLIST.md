# Baby Cloud Deployment Checklist

## Before Git commit
- [ ] frontend build passes
- [ ] backend syntax passes
- [ ] production health route works
- [ ] scheduler status route works
- [ ] monitor routes work
- [ ] stock history works
- [ ] portfolio history works
- [ ] Ask Baby UI works
- [ ] no secrets in Git
- [ ] .env ignored
- [ ] Alpaca PAPER confirmed
- [ ] real money remains DISABLED

## Backend VM
- [ ] Oracle VM created
- [ ] Ubuntu updated
- [ ] repo cloned to /opt/baby
- [ ] Python 3.11 environment created
- [ ] requirements installed
- [ ] .env created manually
- [ ] systemd service installed
- [ ] baby-api starts
- [ ] baby-api enabled at boot
- [ ] local API responds on 127.0.0.1:8787

## Public API
- [ ] API domain configured
- [ ] Caddy installed
- [ ] HTTPS works
- [ ] port 8787 NOT publicly exposed
- [ ] only 80/443 and SSH allowed through firewall
- [ ] allowed frontend origin configured

## Database
- [ ] SQLite is on persistent VM disk
- [ ] nightly backup timer installed
- [ ] backup restore tested once

## Frontend
- [ ] Cloudflare Pages project created
- [ ] root directory = frontend
- [ ] build command = npm run build
- [ ] output directory = dist
- [ ] VITE_BABY_API_BASE_URL configured
- [ ] production UI can call API

## Continuous behavior
- [ ] reboot VM
- [ ] Baby API returns automatically
- [ ] scheduler still enabled
- [ ] 09:15 job can run
- [ ] monitor sync runs
- [ ] DB survives reboot

## Safety
- [ ] Alpaca still PAPER
- [ ] BABY_REAL_MONEY_EXECUTION=DISABLED
- [ ] no automatic order submission enabled
