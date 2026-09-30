# kandepet.com

Hugo site with Remark42 comments, self-hosted on a Hetzner EX44 with Docker Compose.
Pushing to `main` on GitHub rebuilds and publishes the site within seconds.

```
git push ──► GitHub ──webhook──► Caddy /_deploy ──► builder: git pull + hugo ──► /srv/site/current
                                   │
             kandepet.com ◄────────┤ serves static files
    comments.kandepet.com ◄────────┘ proxies to remark42
```

| Path | What |
|---|---|
| `site/` | Hugo source: `content/`, `layouts/` (site overrides), `static/`, `hugo.toml` |
| `site/themes/kandepet` | Theme: a recreation of the old WordPress "Read" theme |
| `deploy/` | `docker-compose.yml`, `Caddyfile`, builder image, env templates |
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

1. **Push this repo to GitHub** (public). Set `REPO_URL` below to its clone URL.
2. **Install Docker** on the EX44: https://docs.docker.com/engine/install/ (Compose plugin included).
3. **Clone and configure:**
   ```bash
   git clone https://github.com/kandepet/kandepet.com.git /opt/kandepet
   cd /opt/kandepet/deploy
   cp .env.example .env                    # ACME_EMAIL, REPO_URL, WEBHOOK_SECRET
   cp remark42.env.example remark42.env    # SECRET, ADMIN_PASSWD, login options
   chmod 600 .env remark42.env
   ```
   Generate secrets with `openssl rand -hex 32`.
4. **Firewall** (Hetzner Robot → Firewall): allow inbound TCP 22, 80, 443 and UDP 443.
5. **DNS:** a day ahead, lower the TTL. Then point `kandepet.com`, `www.kandepet.com` and
   `comments.kandepet.com` (A, and AAAA if the EX44 has IPv6; remove any old AAAA records)
   at the EX44.
6. **Start:**
   ```bash
   docker compose up -d --build
   docker compose logs -f builder caddy    # first build + certificates
   ```
7. **Import the WordPress comments** (once, before anyone comments; the import replaces
   all comments for the site):
   ```bash
   docker compose exec remark42 import -p wordpress -f /srv/import/comments-import.xml -s kandepet --url http://localhost:8080
   ```
8. **GitHub webhook** (repo → Settings → Webhooks → Add):
   Payload URL `https://kandepet.com/_deploy`, content type `application/json`,
   secret = `WEBHOOK_SECRET`, event "Just the push event".
   The ping shows "Hook rules were not satisfied"; that's expected. Real pushes to `main` build.
9. **Make yourself comment admin:** sign in on any post's comment box, click your name to
   see your user ID, put it in `ADMIN_SHARED_ID` in `remark42.env`, then
   `docker compose up -d remark42`.

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
