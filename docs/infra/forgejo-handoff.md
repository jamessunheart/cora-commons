# Handoff: Sovereign git layer (Forgejo), plus agent task priorities

> **Public document.** This file is meant to be committed to the public repo `jamessunheart/cora-commons` at `docs/infra/forgejo-handoff.md`. It contains **placeholders only**: no secrets, hostnames, IPs, tokens, emails or phone numbers. Keep it that way.
>
> Tracks: [cora-commons #25, Sovereign git layer](https://github.com/jamessunheart/cora-commons/issues/25), part of the [#4 build queue](https://github.com/jamessunheart/cora-commons/issues/4).
> Written 2026-10-18 (America/Costa_Rica).

---

## Part 1: Claude Code handoff (paste everything below into Claude Code on James's server)

You are an autonomous coding agent running on a Linux server that James controls. Your job is to stand up a self-hosted **Forgejo** server as a **read-only mirror** of the AI memory repo, plus one Forgejo-only private vault repo that agents can write to. Work through the tasks **in order**. Each task lists what it depends on. Stop and ask James before anything destructive.

### 0. Principles (read first, apply to every step)

1. **GitHub is the primary source of truth. Forgejo is a one-way pull mirror.**
   - Forgejo **pulls** from GitHub on a schedule. Nothing **ever pushes** from Forgejo to GitHub. That way the two can never diverge.
   - Every migration step is a **pull mirror**. No two-way sync, no push mirrors.
   - **Out of scope:** Forgejo push mirrors to GitHub, `git push` from the Forgejo copy to GitHub, and any sync tool that writes back to GitHub. If a step seems to need one, stop and ask James.
2. **Forgejo-only repos are allowed and are not mirrored.** Private-vault repos (for example `cora/cora-vault`) live only on Forgejo. They have no GitHub counterpart, so they can't conflict with principle 1. Agents write here.
3. **Failover is dormant.** Section 7.3 (switching primary to Forgejo) applies **only if James explicitly says to switch primary later.** Until then, writes to the memory repo keep going to GitHub.
4. **James is the sole credential custodian.**
   - Never ask James to paste a password, token or key into chat.
   - Never write a secret into a file inside any git repo, into shell history, or into logs.
   - When a step produces a secret (a password or token), hand that step to James: print the exact command or UI path, and let him run it in his own terminal or browser and store the result in his password manager.
   - Secrets that services need at runtime go in root-only files **outside** any repo (e.g. `/etc/forgejo-secrets/*`, mode `600`), never in `docker-compose.yml`.
5. **Nothing destructive without asking.** That includes deleting data, volumes, users or repos, overwriting configs, `docker compose down -v`, reformatting disks, and changing firewall rules in a way that could lock out SSH.
6. **Public lane vs private lane.** The real domain, IPs, usernames for SSH, restic repo locations and anything host-specific go only in the **private** repo `jamessunheart/cora-memory` (under `infra/forgejo/`) or on the server. The public `cora-commons` repo only ever gets placeholder text like this file.

> **Note on #25's acceptance criteria.** #25 says "an agent can read and commit to the memory repo on the self-hosted server." Under principle 1, the mirrored memory repo on Forgejo is read-only (Forgejo pull mirrors reject pushes). So for now that criterion is met this way: agents **read** the memory repo from the Forgejo mirror, and **commit** to the Forgejo-only `cora-vault` repo. Committing to the memory repo itself on Forgejo only happens after a James-approved primary switch (7.3). Report this to James in your final report.

### Placeholders used below

| Placeholder | Meaning | Where the real value lives |
|---|---|---|
| `${FORGEJO_DOMAIN}` | e.g. `git.<your-domain>` | Server `.env` file plus private repo, never public |
| `${FORGEJO_VERSION}` | Pinned image tag, see 2.1 | `.env` |
| `${ACME_EMAIL}` | Email for TLS certificate notices | `.env` (not a secret, but private) |
| `${FORGEJO_SSH_PORT}` | Host port for git-over-SSH (default `2222`) | `.env` |
| `${ADMIN_SSH_PORT}` | Host SSH port for server admin (default `22`) | `.env` |
| `${RESTIC_REPOSITORY}` | Off-site backup target (S3/B2/SFTP URL) | `/etc/forgejo-secrets/restic.env` |
| `${BACKUP_DIR}` | Local staging dir for dumps, e.g. `/srv/forgejo/backups` | `.env` |
| `${ORG}` | Forgejo org name, suggested `cora` | `.env` |

### Prereqs James provides (before you start)

- [ ] A Linux server or machine he controls (Debian 12/13 or Ubuntu 24.04 LTS recommended; 1 vCPU, 1–2 GB RAM and 20 GB+ disk is plenty for SQLite).
- [ ] SSH access for you to that server with a sudo-capable user (key-based).
- [ ] A domain or subdomain whose DNS **A/AAAA record** points at the server (preferred). If there's no domain yet, use the IP fallback in 3.3.
- [ ] An off-site backup target for restic (S3-compatible bucket, Backblaze B2, or an SFTP box), with credentials that **James** puts in `/etc/forgejo-secrets/restic.env` himself.
- [ ] Later, at step 5: a **GitHub fine-grained personal access token**, read-only, scoped to `jamessunheart/cora-memory` only (Repository permissions: Contents = Read-only, Metadata = Read-only). James types it into the Forgejo migration form himself. You never see it.

---

### Group A: Infrastructure

#### Task 1. Provision and harden the server (depends on: prereqs)

1. Confirm OS and resources: `cat /etc/os-release; nproc; free -h; df -h`.
2. Update packages and enable automatic security updates:
   ```bash
   sudo apt update && sudo apt -y full-upgrade
   sudo apt -y install unattended-upgrades ufw fail2ban curl git sqlite3 restic
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```
3. SSH hardening (ask James before applying, and keep your current session open while testing a second login):
   - `PasswordAuthentication no`, `PermitRootLogin no`, `KbdInteractiveAuthentication no` in `/etc/ssh/sshd_config.d/10-hardening.conf`, then `sudo systemctl reload ssh`.
4. Firewall (ask James first, and make sure the admin SSH port is allowed **before** enabling):
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ${ADMIN_SSH_PORT}/tcp     # admin SSH
   sudo ufw allow 80/tcp                    # ACME HTTP challenge + redirect
   sudo ufw allow 443/tcp                   # HTTPS
   sudo ufw allow ${FORGEJO_SSH_PORT}/tcp   # git over SSH
   sudo ufw enable
   ```
   Note: Docker-published ports can bypass ufw. Only Caddy publishes 80/443 and Forgejo publishes the git SSH port. Forgejo's web port 3000 is **not** published to the host.
5. Install Docker Engine and the compose plugin from Docker's official repo (Forgejo requires Docker ≥ 20.10.6). Docs: https://docs.docker.com/engine/install/
6. Create the layout: `/srv/forgejo/{data,caddy,backups}` and `/etc/forgejo-secrets` (`root:root`, mode `700`). Run `sudo chown -R 1000:1000 /srv/forgejo/data`.

---

### Group B: Install

#### Task 2. Install Forgejo (depends on: 1)

**2.1 Pick and pin a version.** As of 2026-10-18, per https://forgejo.org/releases/:
- **v15.0.10 LTS**, supported until 15 July 2027. **Recommended** for a low-maintenance single-owner server.
- v17.0.0 stable, supported until 28 January 2027 (needs a major upgrade about every 3 months).

Set `FORGEJO_VERSION=15.0.10` in `.env`. Pin the exact patch version, never `latest`. Major upgrades are manual and need a backup first: https://forgejo.org/docs/latest/admin/upgrade/

**2.2 Preferred: Docker + docker compose + SQLite.** SQLite is fine for this scale. Postgres is optional and adds a container and a password to manage. Docs: https://forgejo.org/docs/latest/admin/installation/docker/

Create `/srv/forgejo/docker-compose.yml` (template in Appendix A) and `/srv/forgejo/.env` (Appendix A.2). Then:
```bash
cd /srv/forgejo && sudo docker compose config   # validate
sudo docker compose up -d
sudo docker compose logs -f forgejo              # wait for "Starting new Web server"
```

**2.3 Alternative: binary + systemd.** Use this only if Docker isn't wanted. Docs: https://forgejo.org/docs/latest/admin/installation/binary/
- Download the binary for the pinned version, verify the GPG signature, install to `/usr/local/bin/forgejo`, create the `git` system user, `/var/lib/forgejo` and `/etc/forgejo`, and install the upstream `forgejo.service` unit.
- Apply the same `app.ini` settings as Appendix A's environment block, in `/etc/forgejo/app.ini`.

**2.4 Initial configuration.** The `FORGEJO__security__INSTALL_LOCK=true` env var skips the web installer, so no stranger can claim the instance during the window before you create the admin. Admin creation happens in Task 4.

#### Task 3. HTTPS through a reverse proxy (depends on: 2)

Docs: https://forgejo.org/docs/latest/admin/setup/reverse-proxy/ and https://caddyserver.com/docs/caddyfile

**3.1 Caddy (preferred).** Caddy runs as a container in the same compose file and gets Let's Encrypt certificates automatically. Template in Appendix B.

**3.2 Domain path.** Once DNS points at the server, `https://${FORGEJO_DOMAIN}` should serve Forgejo with a valid certificate. Check it with `curl -sI https://${FORGEJO_DOMAIN} | head -1`.

**3.3 IP fallback (no domain yet).** Public CAs generally won't issue a normal certificate for a bare IP. Use the second Caddyfile block in Appendix B (`tls internal`, Caddy's own CA). Then either:
- Restrict 443 and `${FORGEJO_SSH_PORT}` to a private network (WireGuard or Tailscale) with ufw, **recommended**. Or
- Have James trust Caddy's root certificate on his devices.

Move to a real domain as soon as there is one, and update `ROOT_URL`.

**3.4** Forgejo's `ROOT_URL` must equal the public HTTPS URL, and `SSH_DOMAIN`/`SSH_PORT` must match what clients use. Both are set in Appendix A.

---

### Group C: Security

#### Task 4. Accounts and SSH key access (depends on: 3)

1. **James's admin account.** James sets this password himself. Print this command for **James** to run in his own terminal (it prompts or prints a password, so you must not run it):
   ```bash
   sudo docker exec -it -u git forgejo forgejo admin user create \
     --admin --username <james-admin-username> --email <james-email> \
     --random-password --must-change-password=true
   ```
   James logs in at `https://${FORGEJO_DOMAIN}`, changes the password, and **enables 2FA (TOTP)** under Settings → Security. He stores the password and recovery codes in his password manager.
2. **Bot user `grok-bot` (not an admin).** James runs this too, or creates the user in Site administration → User accounts:
   ```bash
   sudo docker exec -it -u git forgejo forgejo admin user create \
     --username grok-bot --email <bot-noreply-email> \
     --random-password --must-change-password=false
   ```
   James stores the bot's password in his password manager (it's only needed for recovery).
3. **Organization and team.** As James's admin (James clicks, or you use the API with a short-lived admin token **that James creates, uses and revokes himself**):
   - Create org `${ORG}` (suggested `cora`), visibility **private**.
   - Create team `agents` in `${ORG}` with **no** "access all repositories". Add `grok-bot`. Repo grants are in Task 6.
4. **SSH keys.**
   - James adds **his own public key** to his Forgejo account (Settings → SSH/GPG keys).
   - For the bot: generate a dedicated keypair on the machine that runs the agent, e.g. `ssh-keygen -t ed25519 -C grok-bot -f ~/.ssh/grok-bot_ed25519`. Add **only the public key** to the `grok-bot` account. The private key never leaves that machine and never enters a repo.
   - Test: `ssh -T -p ${FORGEJO_SSH_PORT} git@${FORGEJO_DOMAIN}` should greet the right user.
   - Docs: https://forgejo.org/docs/latest/admin/installation/docker/ (SSH section)
5. **Bot access token.** James logs in as `grok-bot` (or uses an admin-run `forgejo admin user generate-access-token` in his own terminal) and creates a token named `grok-bot-agent` with **only** these scopes:
   - `write:repository` (read and write repo contents, PRs and branches on repos the bot can access)
   - `read:user`
   - Add `read:organization` only if the MCP or tool needs to list org repos.

   Scopes docs: https://forgejo.org/docs/latest/user/token-scope/ · API docs: https://forgejo.org/docs/latest/user/api-usage/

   James copies the token into (a) his password manager and (b) Grok Bot's secure secret prompt. **Never into a file in any repo, a chat, or a log.** Record only *where* it's stored (Task 7).

#### Task 6. Branch protection and security defaults (depends on: 4, 5)

1. **Repo access, least privilege.**
   - `agents` team: **Read** on the `cora-memory` mirror, **Write** on `cora-vault`. No access to anything else.
   - No admin rights for `grok-bot` anywhere.
2. **Create the Forgejo-only vault repo** `${ORG}/cora-vault`: private, initialized with a README, default branch `main`. Not a mirror, and never push-mirrored to GitHub.
3. **Branch protection on `cora-vault` `main`** (Settings → Branches). Docs: https://forgejo.org/docs/latest/user/protection/
   - Disable force-push and branch deletion.
   - Require a pull request to merge into `main`. `grok-bot` may push to non-`main` branches and open PRs, and James (or an approved rule) merges. If James prefers the bot to commit straight to `main`, add `grok-bot` to the push allowlist **only on his say-so**.
   - Mirror repos are read-only by design, so no protection rule is needed there.
4. **Server security defaults** (already in Appendix A's env block; verify them in Site administration → Configuration). Docs: https://forgejo.org/docs/latest/admin/config-cheat-sheet/
   - `service.DISABLE_REGISTRATION=true` (open registration off)
   - `service.REQUIRE_SIGNIN_VIEW=true` (nothing visible without login)
   - `service.DEFAULT_KEEP_EMAIL_PRIVATE=true`
   - `repository.DEFAULT_PRIVATE=private`, `repository.ENABLE_PUSH_CREATE_USER=false`, `repository.ENABLE_PUSH_CREATE_ORG=false`
   - `openid.ENABLE_OPENID_SIGNIN=false`, `openid.ENABLE_OPENID_SIGNUP=false`
   - `security.INSTALL_LOCK=true`
   - `mirror.DEFAULT_INTERVAL=10m` (pull frequency; the minimum is 10m)
   - Forgejo Actions off unless needed: `actions.ENABLED=false`
5. **Backups: nightly, encrypted, off-site** (Appendix C):
   - `forgejo dump` (files + SQLite DB) → local `${BACKUP_DIR}` → `restic backup` to `${RESTIC_REPOSITORY}`, encrypted with a restic password that **James** sets in `/etc/forgejo-secrets/restic.env` (mode `600`). Retention: 7 daily, 4 weekly, 6 monthly.
   - Schedule it with a systemd timer (Appendix C.2) at about 03:30 server time.
   - **Run one test restore** (Appendix C.3) into a throwaway directory and a throwaway container on a different port. Confirm the mirrored repo and `cora-vault` open and `git fsck` passes. Then remove **only** the throwaway container and directory, after telling James.
   - Dump docs: https://forgejo.org/docs/latest/admin/command-line/ (`forgejo dump`)
6. **Health check.**
   - `curl -fsS https://${FORGEJO_DOMAIN}/api/healthz` should return a `pass` status.
   - Add a systemd timer or cron job that runs it every 5 min and logs failures. Optionally ping an uptime service (its URL goes in the secrets dir).
   - Run `sudo docker exec -u git forgejo forgejo doctor check --all` after install and after each upgrade.
7. **Updates.** Patch releases: change `FORGEJO_VERSION`, back up, `docker compose pull && docker compose up -d`, then run doctor. Watch security announcements: https://codeberg.org/forgejo/security-announcements

---

### Group D: Migration

#### Task 5. Pull-mirror `cora-memory` from GitHub (depends on: 4)

**Pull mirror only.** Docs: https://forgejo.org/docs/latest/user/repo-mirror/ ("Pulling from a remote repository")

1. James creates the GitHub fine-grained token (read-only Contents + Metadata, only `jamessunheart/cora-memory`, expiry 90 days or less) and stores it in his password manager.
2. James, logged in as admin, goes to **+ → New Migration → GitHub** and enters:
   - Clone URL: `https://github.com/jamessunheart/cora-memory.git`
   - Access token: the fine-grained token, **typed by James**
   - Owner: `${ORG}`, repo name `cora-memory`, visibility **Private**
   - ✅ **"This repository will be a mirror"** (this is what makes it a pull mirror)
   - Migrate code only. Issues, PRs and wiki are optional; code is enough.
3. Confirm in repo Settings → Mirror settings that the interval is `10m` and the **Push mirrors section stays empty.**
4. Verify it's in sync: the latest commit SHA on Forgejo `main` equals GitHub `main` (`git ls-remote` against both). Click **Synchronize now** once.
5. `cora-commons` (public) is optional and gets the same treatment, as a pull mirror only.
6. **Out of scope:** push mirrors, two-way sync, and making the Forgejo copy writable. You can't convert a pull mirror into a normal repo without a James-approved primary switch (7.3).
7. Token rotation: when the GitHub token expires, James updates it in the mirror settings. Note the expiry date location in Task 7 (the date, not the token).

---

### Group E: Docs

#### Task 7. Document access URLs and where credentials live (depends on: 1–6)

1. **Infra as code, private lane.** Commit `docker-compose.yml`, `Caddyfile`, `backup.sh`, the systemd units and `.env.example` (placeholders only) to the **private** repo `jamessunheart/cora-memory` under `infra/forgejo/`, via a branch and PR for James. Never commit `.env` or anything under `/etc/forgejo-secrets`. Add `infra/forgejo/.gitignore` with `.env` and `*.secret`.
   - Because `cora-memory` is mirrored, this PR goes to **GitHub** and flows to Forgejo by pull. Never commit it on Forgejo.
2. **`infra/forgejo/RUNBOOK.md` (private repo).** It covers:
   - Access URLs: web `https://${FORGEJO_DOMAIN}`, git SSH `ssh://git@${FORGEJO_DOMAIN}:${FORGEJO_SSH_PORT}/<org>/<repo>.git`, API `https://${FORGEJO_DOMAIN}/api/v1`. Real values are OK here because it's private.
   - **A credential locations table: locations only, never values.**

     | Credential | Stored where | Who holds it |
     |---|---|---|
     | Forgejo admin password + 2FA recovery codes | James's password manager | James |
     | `grok-bot` password | James's password manager | James |
     | `grok-bot-agent` API token | James's password manager + Grok Bot secret prompt | James |
     | `grok-bot` SSH private key | Agent machine `~/.ssh/` only | The agent machine |
     | GitHub fine-grained read token (mirror) | Forgejo mirror settings + James's password manager; expiry date noted | James |
     | restic password + backup target credentials | `/etc/forgejo-secrets/restic.env` (root, 600) + James's password manager | James |
     | Server SSH/root access | James's devices / password manager | James |
   - The upgrade procedure, the backup/restore procedure, and the date of the last successful restore test.
3. **7.3 Failover / primary switch (dormant).** Applies only if James explicitly decides to make Forgejo primary. Draft the steps, don't run them:
   1. Freeze GitHub writes.
   2. Final sync.
   3. Convert the mirror to a normal repo (in Forgejo you migrate a fresh, non-mirror copy).
   4. Point agents at Forgejo.
   5. Decide whether GitHub becomes a downstream mirror or is archived.

   This reverses principle 1, and #25's "GitHub mirror status (keep as backup, or drop)" decision belongs to James.

---

### Verification checklist (all must pass)

- [ ] `https://${FORGEJO_DOMAIN}` loads with a valid TLS certificate (or `tls internal` over the private network in the IP fallback); HTTP redirects to HTTPS.
- [ ] Port 3000 isn't reachable from outside; only 80, 443, `${FORGEJO_SSH_PORT}` and admin SSH are open.
- [ ] Logged out, the instance shows a login page only. Registration is disabled (`/user/sign_up` refuses).
- [ ] James's admin account exists, its password was set by James, and 2FA is on.
- [ ] `grok-bot` exists, is **not** an admin, and only belongs to `agents`.
- [ ] `${ORG}/cora-memory` is a **pull mirror**, private, with an interval of 10m. Its `main` SHA matches GitHub, and the push-mirror list is **empty**.
- [ ] Using the bot token: `GET /api/v1/repos/${ORG}/cora-memory/contents/README.md` succeeds (read); a push to the mirror is rejected; a branch + commit + PR on `${ORG}/cora-vault` succeeds; a direct push to `cora-vault` `main` is rejected (unless James allowlisted it).
- [ ] The bot SSH key can clone `cora-memory` and push a branch to `cora-vault`.
- [ ] The bot token can't access the admin API (`GET /api/v1/admin/users` → 403).
- [ ] The nightly backup timer is enabled, and one backup has landed in `${RESTIC_REPOSITORY}` (`restic snapshots`).
- [ ] The test restore succeeded (repos open, `git fsck` clean), and the throwaway instance was removed.
- [ ] Health check returns pass; `forgejo doctor check --all` is clean.
- [ ] Unattended upgrades and fail2ban are active.
- [ ] `infra/forgejo/` PR is open on GitHub `cora-memory` with no secrets (scan the diff for anything token-shaped before opening it).
- [ ] No secret, hostname or IP appears in any public repo, chat message or log you produced.

### Final report to return to James

Reply with exactly this, filling in the blanks. **No secret values.**

```
Forgejo setup report
- Version: Forgejo <x.y.z> (Docker | binary), DB: SQLite
- Web URL: https://<domain>   (private; don't paste into public repos)
- Git SSH: port <n>
- Admin account: created, password set by James, 2FA: <on/off>
- Bot username: grok-bot (non-admin, team "agents")
- Bot token: name "grok-bot-agent", scopes <list>; stored in: James's password manager + Grok Bot secret prompt (value not seen by me)
- Mirror: <org>/cora-memory ← GitHub, pull-only, interval 10m, last sync <time, America/Costa_Rica>, push mirrors: none
- Vault: <org>/cora-vault, Forgejo-only, main protected
- Backups: nightly forgejo dump + restic → <type: S3 / B2 / SFTP>, retention 7d/4w/6m
- Restore test: <pass/fail>, <date>, what was checked
- Health check: <pass/fail>; doctor: <clean/issues>
- Infra-as-code PR: <link to private cora-memory PR>
- #25 acceptance: read via mirror ✅ / commit via cora-vault ✅ / GitHub mirror status: James to decide
- Open questions / anything I stopped short of:
```

---

### Appendix A: `docker-compose.yml` (template, placeholders only)

```yaml
# /srv/forgejo/docker-compose.yml : copy into cora-memory infra/forgejo/ (private). No secrets in this file.
networks:
  forgejo:
    external: false

services:
  forgejo:
    image: codeberg.org/forgejo/forgejo:${FORGEJO_VERSION}
    container_name: forgejo
    restart: unless-stopped
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - FORGEJO__database__DB_TYPE=sqlite3
      - FORGEJO__server__DOMAIN=${FORGEJO_DOMAIN}
      - FORGEJO__server__ROOT_URL=https://${FORGEJO_DOMAIN}/
      - FORGEJO__server__HTTP_PORT=3000
      - FORGEJO__server__SSH_DOMAIN=${FORGEJO_DOMAIN}
      - FORGEJO__server__SSH_PORT=${FORGEJO_SSH_PORT}
      - FORGEJO__server__SSH_LISTEN_PORT=22
      - FORGEJO__security__INSTALL_LOCK=true
      - FORGEJO__service__DISABLE_REGISTRATION=true
      - FORGEJO__service__REQUIRE_SIGNIN_VIEW=true
      - FORGEJO__service__DEFAULT_KEEP_EMAIL_PRIVATE=true
      - FORGEJO__repository__DEFAULT_PRIVATE=private
      - FORGEJO__repository__ENABLE_PUSH_CREATE_USER=false
      - FORGEJO__repository__ENABLE_PUSH_CREATE_ORG=false
      - FORGEJO__openid__ENABLE_OPENID_SIGNIN=false
      - FORGEJO__openid__ENABLE_OPENID_SIGNUP=false
      - FORGEJO__mirror__DEFAULT_INTERVAL=10m
      - FORGEJO__actions__ENABLED=false
    volumes:
      - ./data:/data
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "${FORGEJO_SSH_PORT}:22"   # git over SSH; web port 3000 is NOT published
    networks:
      - forgejo

  caddy:
    image: caddy:2
    container_name: caddy
    restart: unless-stopped
    environment:
      - FORGEJO_DOMAIN=${FORGEJO_DOMAIN}
      - ACME_EMAIL=${ACME_EMAIL}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy/data:/data
      - ./caddy/config:/config
    networks:
      - forgejo
    depends_on:
      - forgejo
```

**A.2 `.env.example`** (commit this; the real `.env` stays on the server, mode `600`):
```dotenv
FORGEJO_VERSION=15.0.10
FORGEJO_DOMAIN=git.example.invalid
ACME_EMAIL=admin@example.invalid
FORGEJO_SSH_PORT=2222
ADMIN_SSH_PORT=22
BACKUP_DIR=/srv/forgejo/backups
ORG=cora
```

### Appendix B: `Caddyfile` (template)

```caddyfile
# Domain path (preferred): automatic Let's Encrypt certificate
{
	email {$ACME_EMAIL}
}

{$FORGEJO_DOMAIN} {
	encode zstd gzip
	reverse_proxy forgejo:3000
	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
	}
}

# IP fallback (no domain yet): replace the block above with this one,
# and restrict 443 to a private network (WireGuard/Tailscale) via ufw.
# https://{$FORGEJO_IP} {
# 	tls internal
# 	reverse_proxy forgejo:3000
# }
```

### Appendix C: Backups

**C.1 `backup.sh`** (install to `/usr/local/sbin/forgejo-backup.sh`, root `700`):
```bash
#!/usr/bin/env bash
# Nightly Forgejo backup: forgejo dump -> restic (encrypted, off-site).
# Secrets come from /etc/forgejo-secrets/restic.env (RESTIC_REPOSITORY, RESTIC_PASSWORD_FILE,
# plus provider creds such as AWS_ACCESS_KEY_ID/B2_ACCOUNT_ID). Never commit that file.
set -euo pipefail
source /srv/forgejo/.env
set -a; source /etc/forgejo-secrets/restic.env; set +a

STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

# 1. Consistent dump of repos + SQLite DB + config, written inside the data volume
docker exec -u git forgejo forgejo dump --type tar.gz \
  --file "/data/backup-tmp/forgejo-dump-${STAMP}.tar.gz" --tempdir /data/backup-tmp \
  || { echo "dump failed"; exit 1; }
mv "/srv/forgejo/data/backup-tmp/forgejo-dump-${STAMP}.tar.gz" "${BACKUP_DIR}/"

# 2. Encrypted off-site copy (dump + compose/Caddy config; NOT /etc/forgejo-secrets)
restic backup --tag forgejo "${BACKUP_DIR}/forgejo-dump-${STAMP}.tar.gz" \
  /srv/forgejo/docker-compose.yml /srv/forgejo/Caddyfile

# 3. Retention, remote and local
restic forget --tag forgejo --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
find "${BACKUP_DIR}" -name 'forgejo-dump-*.tar.gz' -mtime +3 -delete

# 4. Light integrity check
restic check --read-data-subset=5%
echo "backup ok ${STAMP}"
```
Before the first run: `mkdir -p /srv/forgejo/data/backup-tmp && chown 1000:1000 /srv/forgejo/data/backup-tmp`. James runs `restic init` once, with his own password.

**C.2 systemd timer:**
```ini
# /etc/systemd/system/forgejo-backup.service
[Unit]
Description=Forgejo nightly backup
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/forgejo-backup.sh

# /etc/systemd/system/forgejo-backup.timer
[Unit]
Description=Run Forgejo backup nightly
[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=15m
Persistent=true
[Install]
WantedBy=timers.target
```
Enable with `sudo systemctl daemon-reload && sudo systemctl enable --now forgejo-backup.timer`.

**C.3 Test restore (run once, report the result):**
```bash
set -a; source /etc/forgejo-secrets/restic.env; set +a
T=/tmp/forgejo-restore-test && mkdir -p $T
restic restore latest --tag forgejo --target $T
DUMP=$(find $T -name 'forgejo-dump-*.tar.gz' | head -1)
mkdir -p $T/unpacked && tar -xzf "$DUMP" -C $T/unpacked
ls $T/unpacked                                   # expect: app.ini, forgejo-db.sql, repos/, data/ ...
for r in $(find $T/unpacked/repos -maxdepth 2 -name '*.git'); do git -C "$r" fsck --no-progress && echo "fsck ok $r"; done
# Optional full check: start a throwaway forgejo:${FORGEJO_VERSION} container on port 3999 bound to 127.0.0.1,
# restore data + DB into it per the dump layout, log in, and confirm cora-memory + cora-vault are present.
# Afterwards, tell James and remove ONLY $T and the throwaway container.
```

---

## Part 2: Agent task priorities (#4 build queue, all 18 open items)

As of 2026-10-18. Owner: **agent** = an AI agent can finish it; **James** = needs his sign-in, credential or resonance; **both** = an agent finishes once James's step is done.

**Order changes vs. #4's "Next up" (#19, then #5):**
- **#23 moved to the top** because it's nearly done (draft PR exists, and Bobby is reachable already).
- **#11 moved up** because the Suno sign-in is done, so it only needs James to pick a take, and it unblocks #12.
- **#24 and #25 sit mid-queue**, matching #25's own "after #24 and #23" note and James's push toward voice and GitHub-as-memory.

Everything else keeps #4's order.

| Rank | Issue | Title | Owner | Blocked by | Next action | Why |
|---|---|---|---|---|---|---|
| 1 | #23 | WhatsApp bridge: contact directory for direct chats | both | Michael's number (James) | James sends Michael's number; agent adds it to cora-memory PR #9; James resonates and merges | Nearly done; unlocks sending by name, including by voice |
| 2 | #19 | Create the private lane repo (first angel-builder mission) · needs-human | James | James's repo creation/decision | James confirms whether `cora-memory` already serves as the private lane or creates the repo; agent scaffolds it | #4 "Next up"; keeps keys and private info off the public repo |
| 3 | #11 | Suno sign-in (no Google), then generate the "A Slice of God" song · needs-human | James | James picking the take | James listens and picks the best take; agent keeps it and closes the sign-in step | Sign-in done; one resonance unlocks #12 |
| 4 | #5 | Connect YouTube to Postiz · needs-human, agent-ready | James | YouTube sign-in in Postiz (James or a trusted angel) | James connects YouTube in Postiz | #4 "Next up"; unlocks #7 and the first stream |
| 5 | #6 | Provide the Postiz Public API key to Grok Bot · needs-human | James | James | James pastes the key into the secure secret card only | Lets agents drive Postiz without James |
| 6 | #7 | Upload "A Slice of God" to YouTube as private/unlisted, send James the link | agent | #5, #6 | Agent uploads private/unlisted and sends the link | First release becomes watchable for resonance |
| 7 | #12 | Score the video with the Suno song | agent | #11 | Agent scores the film with the chosen take | Turns the silent film into the full release |
| 8 | #8 | Make 9:16 vertical versions for Shorts, Reels, TikTok and Pinterest | both | James's resonance on the open PR | James resonates; agent finalizes the versions | Needed for every short-form channel |
| 9 | #24 | WhatsApp voice notes → Grok Bot routine webhook (voice front door) | both | Bridge code location (James); webhook key into private lane (James) | James names the Brain/bridge repo; agent builds the routine and a draft PR for the hook | Voice front door while laptop audio is down |
| 10 | #25 | Sovereign git layer: self-hosted Forgejo mirror for the AI memory · needs-human | both | A server + domain from James | James provisions the server and runs this handoff in Claude Code | Sovereign, private copy of the AI memory; GitHub stays primary |
| 11 | #9 | Connect remaining channels in Postiz · needs-human | James | James's channel sign-ins | James connects Instagram, TikTok, Facebook, LinkedIn, Threads, Bluesky, Pinterest | Reach beyond YouTube |
| 12 | #10 | Create Postiz drafts for each connected channel (never published) | agent | #9 (and #8 for verticals) | Agent drafts per channel; nothing published | Ready-to-go posts waiting on James's yes |
| 13 | #13 | Free trial link and destination for Sunstream releases | agent | Destination decision | Agent proposes the destination and link copy ("Donations coming soon") | Gives viewers somewhere to land |
| 14 | #21 | Braille Book Architecture: shared markdown memory for AI agents | agent | — | Agent drafts the layout in cora-memory | Matches the GitHub-as-memory direction; ports to Forgejo unchanged |
| 15 | #20 | The Angel Builder Protocol (recruit, track, reward with GitHub as-is) · needs-human | both | #19 | Agent drafts the protocol; James approves | Lets humans pick up the needs-human items |
| 16 | #18 | Mission System: rewardable human + agent missions (public and private lanes) | agent | #19, #20 | Agent specs the mission format after #20 | Scales the angel model |
| 17 | #17 | CORA payment rule for the generate-resonate-circulate loop (Angels) | James | James's decision | James resonates with a rule; agent writes it up | Needed before any rewards flow |
| 18 | #14 | Donations coming soon: future donation-only setup (parked) | — | Parked by design | None until James unparks it | Copy says "Donations coming soon" for now |

**Not yet in #4, lowest priority:** the nightly AppFlowy sync is blocked because the AppFlowy grids lack the TASK-012 fields (plus "Notion URL" and "Next Action"). James's direction is GitHub as the primary store, with AppFlowy and Notion as human views, so this waits. File it only if James wants it back in the queue.

**Needs-human items:** #5, #6, #9, #11, #19, #20, #25. Plus the James-only steps inside #23 (Michael's number), #24 (bridge location, webhook key), #8 (resonance) and #17 (decision).
