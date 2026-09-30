# kandepet.com

Hugo site with Remark42 comments, self-hosted on a Hetzner EX44 with Docker Compose,
behind the server's existing nginx (which also serves labs.cx).
Pushing to `main` on GitHub rebuilds and publishes the site within seconds.

```
                    host nginx :443 (HTTPS via certbot)
                        │  kandepet.com, www, comments
                        ▼
git push ──► GitHub ──► Caddy 127.0.0.1:8095 ──/_deploy──► builder: git pull + hugo ──► /srv/site/current
                        │
     kandepet.com ◄─────┤ static files from /srv/site/current
comments.kandepet.com ◄─┘ proxies to remark42
```

| Path | What |
|---|---|
| `site/` | Hugo source: `content/`, `layouts/` (site overrides), `static/`, `hugo.toml` |
| `site/themes/kandepet` | Theme: a recreation of the old WordPress "Read" theme |
| `deploy/` | `docker-compose.yml`, `Caddyfile`, builder image, env templates, `nginx/` site config |
| `migration/` | One-time WordPress conversion script and the comment import file |

## Writing

```bash
brew install hugo                      # use the same version as deploy/builder/Dockerfile
cd site
hugo new content posts/my-new-post.md  # creates a draft
hugo server -D                         # http://localhost:1313, live reload
```

Set `draft: false` (or delete the line), commit and push. The server builds `main`.

Posts live at `/<slug>/`, projects at `/portfolio/<slug>/`, matching the old WordPress URLs.
Put images in `site/static/images/` and reference them as `/images/...`.

## Testing locally

**Quick preview (content and theme):** `cd site && hugo server -D`. Comments don't load
here: production Remark42 only allows embedding on kandepet.com.

**Full stack (Caddy + builder + Remark42, same images as production):** needs Docker
(OrbStack or Docker Desktop). The builder clones your *committed* local repo, so commit
first (no push needed).

```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file local.env up --build
```

- Site: http://localhost:8080, comments service: http://localhost:8081
- Import the WordPress comments:
  `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file local.env exec remark42 import -p wordpress -f /srv/import/comments-import.xml -s kandepet --url http://localhost:8080`
- Commit a change, then trigger a rebuild the way GitHub would: `./test-webhook.sh`
- Stop: `Ctrl-C`; wipe local data: `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file local.env down -v`

The local stack differs from production only by the values in `local.env` and
`docker-compose.local.yml` (plain HTTP on localhost, repo from disk, `site/config/local/`).

## Theme

`site/themes/kandepet` recreates the look of the old WordPress site ("Read" theme):
Josefin Slab for the site title, Coustard for the menu and headings, Lora for text,
self-hosted from `static/fonts/`. It's plain HTML templates and one stylesheet:

| File | What |
|---|---|
| `assets/css/main.css` | All styling; colors and fonts are variables at the top |
| `layouts/baseof.html`, `_partials/header.html`, `_partials/footer.html` | Page frame, title and menu |
| `layouts/home.html`, `list.html`, `_partials/summary.html` | Post lists (featured image, intro, "Continue reading") |
| `layouts/single.html`, `_partials/post-meta.html` | Post page, "posted in … on … by …" line, previous/next links |
| `layouts/archives.html`, `taxonomy.html`, `404.html` | Archives, category index, not found |

- Menu entries are in `[menus]` in `site/hugo.toml`.
- A post's featured image is `image:` in its front matter; the text on the home page is
  `summary:` (or the first paragraph if there's none).
- Comments are wired in from the site, not the theme: `site/layouts/_partials/comments.html`,
  `comment-count.html` and `comment-count-script.html` override empty hooks in the theme.
  Any other theme works too if it calls `partial "comments.html"` on post pages.
- Don't change `[permalinks]` in `hugo.toml`: comments are attached to page URLs.

## Server setup (one time)

Completed 2026-09-30: live at https://kandepet.com on the EX44, HTTPS via certbot,
GitHub webhook active.

The EX44 already runs nginx on ports 80/443 (labs.cx, notes.labs.cx). nginx stays in charge:
it gets the HTTPS certificates with certbot and forwards kandepet.com traffic to this stack,
which listens only on `127.0.0.1:8095`. Nothing about the existing sites changes.

Run these on the server, as your normal user with sudo.

**1. Check what's installed.**
```bash
nginx -v; ls /etc/nginx/sites-enabled /etc/nginx/conf.d
certbot --version
docker --version && docker compose version
```
- If Docker is missing: https://docs.docker.com/engine/install/ubuntu/ (or `/debian/`), then
  `sudo usermod -aG docker $USER` and log in again.
- If certbot is missing: `sudo apt install certbot python3-certbot-nginx`.

**2. Clone the repo and add the secrets.**
```bash
sudo mkdir -p /opt/kandepet && sudo chown $USER: /opt/kandepet
git clone https://github.com/Kandepet/kandepet.com.git /opt/kandepet
cd /opt/kandepet/deploy
cp .env.example .env                    # set WEBHOOK_SECRET
cp remark42.env.example remark42.env    # set SECRET and ADMIN_PASSWD
chmod 600 .env remark42.env
```
Generate each secret with `openssl rand -hex 32`. Keep `WEBHOOK_SECRET` handy for step 9.

**3. Start the stack.**
```bash
docker compose up -d --build
docker compose logs -f builder          # wait for "live: ...", then Ctrl-C
curl -s -H 'Host: kandepet.com' http://127.0.0.1:8095/ | grep -o '<title>.*</title>'
```
The last command should print `<title>Deepak Kandepet</title>`.

**4. Import the WordPress comments** (once, before anyone comments; an import replaces all
comments for the site):
```bash
docker compose exec remark42 import -p wordpress -f /srv/import/comments-import.xml -s kandepet --url http://localhost:8080
```

**5. Add the nginx site.**
```bash
sudo cp /opt/kandepet/deploy/nginx/kandepet.com.conf /etc/nginx/sites-available/kandepet.com
sudo ln -s /etc/nginx/sites-available/kandepet.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
If your nginx uses `conf.d/` instead of `sites-enabled/`, copy it to
`/etc/nginx/conf.d/kandepet.com.conf` instead. It only answers for the kandepet.com names.

**6. Preview before switching DNS (optional).** On your Mac, add this line to `/etc/hosts`
(`sudo nano /etc/hosts`), using the EX44's IP:
```
<EX44-IP>  kandepet.com www.kandepet.com comments.kandepet.com
```
Open **http**://kandepet.com (no HTTPS yet, and comments won't load until step 8).
Remove the line when you're done.

**7. Switch DNS** (Hostinger → Domains → kandepet.com → DNS). A day ahead, lower the TTL
of these records to 300. Then:
- `@`: replace both A records with one A record → EX44 IPv4. Delete both AAAA records
  (or replace them with one AAAA → EX44 IPv6, if the server has one and nginx listens on IPv6).
- `www`: delete the CNAME to Hostinger's CDN; add an A record → EX44 IPv4 (and AAAA if used).
- `comments`: add an A record → EX44 IPv4 (and AAAA if used).

Wait until `dig +short kandepet.com www.kandepet.com comments.kandepet.com` shows only
the EX44's address (usually a few minutes).

**8. Turn on HTTPS.** certbot gets the certificate, adds it to the nginx site, redirects
HTTP to HTTPS, and renews automatically:
```bash
sudo certbot --nginx -d kandepet.com -d www.kandepet.com -d comments.kandepet.com --redirect
systemctl list-timers | grep certbot    # the renewal timer
```
Between the DNS switch and this step, https://kandepet.com shows a certificate error,
so run it as soon as step 7 finishes.

**9. GitHub webhook** (github.com/Kandepet/kandepet.com → Settings → Webhooks → Add webhook):
Payload URL `https://kandepet.com/_deploy`, content type `application/json`,
secret = `WEBHOOK_SECRET`, "Just the push event". The first delivery ("ping") shows
"Hook rules were not satisfied"; that's expected. Push a commit to confirm a real build.

**10. Make yourself comment admin.** Sign in on any post's comment box, click your name to
see your user ID (e.g. `github_…` or `anonymous_…`), put it in `ADMIN_SHARED_ID` in
`remark42.env`, then `docker compose up -d remark42`.

**11. Retire WordPress** once you're happy: take a final backup in Hostinger, then cancel
the hosting. It was compromised (spam links were injected into pages), so change the
Hostinger account password too.

## Operations

All from `/opt/kandepet/deploy`:

| Task | Command |
|---|---|
| Rebuild now | `docker compose exec builder /app/build.sh` |
| Build logs | `docker compose logs -f builder` |
| Roll back | `docker compose exec builder ls /srv/site/releases`, then `docker compose exec builder ln -sfn releases/<name> /srv/site/current` (or `git revert` and push) |
| Deploy config changes | `git -C /opt/kandepet pull && docker compose up -d --build` |
| Reload Caddy only | `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` |
| Back up comments | `docker compose cp remark42:/srv/var/backup ./remark42-backup` (Remark42 writes a daily backup; copy it off the server) |

Only the comments need backing up; the site itself is in git.

## Migration notes

`migration/wp2hugo.py` converted the WordPress export (2026-09-30): 8 posts, 7 portfolio
projects and the About page; downloaded 77 images (including archived copies of imgur
images); wrote the 10 approved comments (names and text only) to
`migration/comments-import.xml`; and generated `deploy/caddy/wp-redirects.caddy` for old
`?p=ID` / `/feed/` URLs. The demo pages and drafts left over from the old theme were skipped.
It is not meant to be rerun: it would overwrite any edits made to the converted posts since.
