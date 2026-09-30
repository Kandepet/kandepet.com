#!/usr/bin/env python3
"""One-time migration of the kandepet.com WordPress export (WXR) to Hugo.

Produces:
  site/content/posts/<slug>.md         published posts   -> /<slug>/
  site/content/portfolio/<slug>.md     published projects -> /portfolio/<slug>/
  site/content/about-me.md             About page
  site/static/wp-content/uploads/...   images from kandepet.com (same paths as before)
  site/static/images/external/...      archived copies of imgur / old-domain images
  migration/comments-import.xml        approved comments only, for `remark42 import -p wordpress`
  deploy/caddy/wp-redirects.caddy      redirects for old WordPress URLs (?p=ID, /feed/, ...)

Usage:
  python3 -m venv .venv && .venv/bin/pip install -r migration/requirements.txt
  .venv/bin/python migration/wp2hugo.py path/to/export.xml [--fetch-media]
"""

import argparse
import hashlib
import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from markdownify import MarkdownConverter

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE_URL = "https://kandepet.com"
# Hosts that served this blog in the past; links to them become site-relative.
OWN_HOSTS = {"kandepet.com", "www.kandepet.com", "nextbighack.com", "www.nextbighack.com"}
# External image hosts worth archiving locally (imgur deletes old images).
ARCHIVE_HOSTS = {"i.imgur.com", "imgur.com", "nextbighack.com", "www.nextbighack.com"}
KEEP_PAGES = {"about-me"}

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
}

media = {}  # original absolute URL -> local site path


def text(el, path):
    return (el.findtext(path, namespaces=NS) or "").strip()


def postmeta(item, key):
    for m in item.findall("wp:postmeta", NS):
        if text(m, "wp:meta_key") == key:
            return text(m, "wp:meta_value")
    return ""


# ---------------------------------------------------------------- cleanup ---

def strip_injected_spam(body):
    # Hidden SEO-spam blocks injected into the WordPress DB, e.g.
    # <!--18644--><div style="position:absolute;left:-12380px">...</div><!--18644-->
    body = re.sub(r"<!--(\d+)-->.*?<!--\1-->", "", body, flags=re.S)
    body = re.sub(r'<div[^>]*style="[^"]*position:\s*absolute;\s*left:\s*-\d+px[^"]*"[^>]*>.*?</div>',
                  "", body, flags=re.S | re.I)
    return body


def convert_shortcodes(body):
    body = re.sub(r'\[gist id="?(\w+)"?[^\]]*\]', r"<p>HUGOGIST\1</p>", body)
    body = re.sub(r"\[/?portfolio_text\]", "", body)
    body = re.sub(r"\[divider\]", "", body)
    body = re.sub(r"\[social_icons\].*?\[/social_icons\]", "", body, flags=re.S)
    return body


BLOCK = r"(?:table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt|ul|ol|li|pre|form|map|area|blockquote|address|math|style|p|h[1-6]|hr|fieldset|legend|section|article|aside|hgroup|header|footer|nav|figure|figcaption|details|menu|summary)"


def wpautop(body):
    """Minimal port of WordPress' wpautop for posts written in the classic editor."""
    pres = []

    def keep_pre(m):
        pres.append(m.group(0))
        return f"\x00PRE{len(pres) - 1}\x00"

    body = re.sub(r"<pre.*?</pre>", keep_pre, body, flags=re.S | re.I)
    body = body.replace("\r\n", "\n")
    body = re.sub(rf"(<{BLOCK}[\s/>])", r"\n\n\1", body, flags=re.I)
    body = re.sub(rf"(</{BLOCK}>)", r"\1\n\n", body, flags=re.I)
    out = []
    for chunk in re.split(r"\n\s*\n", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.match(rf"</?{BLOCK}[\s/>]", chunk, re.I) or chunk.startswith("\x00PRE"):
            out.append(chunk)
        else:
            out.append("<p>" + chunk.replace("\n", "<br />\n") + "</p>")
    body = "\n\n".join(out)
    return re.sub(r"\x00PRE(\d+)\x00", lambda m: pres[int(m.group(1))], body)


# ------------------------------------------------------------------ media ---

def local_media_path(url):
    u = urllib.parse.urlparse(url)
    host = u.netloc.lower()
    if host in OWN_HOSTS and u.path.startswith("/wp-content/uploads/"):
        return urllib.parse.unquote(u.path)
    if host in ARCHIVE_HOSTS:
        name = Path(urllib.parse.unquote(u.path)).name or hashlib.sha1(url.encode()).hexdigest()[:12]
        return f"/images/external/{host.replace('www.', '')}/{name}"
    return None


def rewrite_urls(soup):
    for tag, attr in (("img", "src"), ("a", "href"), ("source", "src")):
        for el in soup.find_all(tag):
            url = el.get(attr)
            if not url or not url.startswith(("http://", "https://", "//")):
                continue
            if url.startswith("//"):
                url = "https:" + url
            local = local_media_path(url)
            if local and re.search(r"\.(png|jpe?g|gif|svg|webp|bmp)$", local, re.I):
                media[url] = local
                el[attr] = local
                continue
            u = urllib.parse.urlparse(url)
            if u.netloc.lower() in OWN_HOSTS:
                el[attr] = urllib.parse.urlunparse(("", "", u.path or "/", "", u.query, u.fragment))
            elif u.scheme == "http" and u.netloc.lower() in {"i.imgur.com", "github.com", "gist.github.com"}:
                el[attr] = "https" + url[4:]
        if tag == "img":
            for el in soup.find_all("img"):
                el.attrs.pop("srcset", None)
                el.attrs.pop("sizes", None)


def fetch_media():
    ok = failed = 0
    for url, local in sorted(media.items(), key=lambda kv: kv[1]):
        dest = SITE / "static" / local.lstrip("/")
        if dest.exists():
            ok += 1
            continue
        candidates = [url, url.replace("http://", "https://", 1)]
        u = urllib.parse.urlparse(url)
        if u.netloc.lower() in OWN_HOSTS:  # old-domain uploads may only exist on the current host
            candidates.append(f"{BASE_URL}{u.path}")
        for cand in dict.fromkeys(candidates):
            try:
                req = urllib.request.Request(cand, headers={"User-Agent": "Mozilla/5.0 (kandepet.com migration)"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                    if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
                        raise ValueError(f"unexpected {r.status} {r.headers.get('Content-Type')}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                ok += 1
                break
            except Exception as e:  # noqa: BLE001 - report and try the next candidate
                err = e
        else:
            failed += 1
            print(f"  ! could not fetch {url}: {err}", file=sys.stderr)
    print(f"media: {ok} saved, {failed} failed")


# --------------------------------------------------------------- markdown ---

class Converter(MarkdownConverter):
    def convert_pre(self, el, text, parent_tags):
        code = el.get_text()
        lang = ""
        m = re.search(r"(?:lang(?:uage)?-|brush:\s*)(\w+)", " ".join(el.get("class", [])) + " " + (el.code.get("class", [""])[0] if el.code and el.code.get("class") else ""))
        if m:
            lang = m.group(1)
        fence = "```" if "```" not in code else "~~~~"
        return f"\n\n{fence}{lang}\n{code.rstrip()}\n{fence}\n\n"


def to_markdown(body):
    body = strip_injected_spam(body)
    body = convert_shortcodes(body)
    if "<p>" not in body and "<p " not in body:
        body = wpautop(body)
    soup = BeautifulSoup(body, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for br in soup.find_all("br", class_="clear"):
        br.decompose()
    rewrite_urls(soup)
    md = Converter(heading_style="ATX", bullets="-", escape_underscores=True).convert_soup(soup)
    md = md.replace(" ", " ")
    md = re.sub(r"HUGOGIST(\w+)", r"{{< gist \1 >}}", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def front_matter(fields):
    lines = ["---"]
    for k, v in fields.items():
        if v in (None, "", []):
            continue
        if isinstance(v, list):
            lines.append(f"{k}:")
            lines += [f"  - {yaml_str(x)}" for x in v]
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {yaml_str(str(v))}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def plain_summary(s, limit=240):
    s = " ".join(BeautifulSoup(s, "html.parser").get_text(" ").split())
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "…"


def iso(gmt):
    return gmt.replace(" ", "T") + "Z" if gmt and not gmt.startswith("0000") else ""


# -------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path)
    ap.add_argument("--fetch-media", action="store_true", help="download referenced images into site/static")
    args = ap.parse_args()

    raw = args.export.read_text(encoding="utf-8")
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)  # WordPress exported a stray form feed
    channel = ET.fromstring(raw).find("channel")

    redirects = []
    comment_items = []
    written = []
    for item in channel.findall("item"):
        ptype, status = text(item, "wp:post_type"), text(item, "wp:status")
        slug, pid = text(item, "wp:post_name"), text(item, "wp:post_id")
        if status != "publish" or ptype not in ("post", "portfolio", "page"):
            continue
        if ptype == "page" and slug not in KEEP_PAGES:
            continue

        cats = [html.unescape(c.text or "") for c in item.findall("category") if c.get("domain") == "category"]
        tags = [html.unescape(c.text or "") for c in item.findall("category")
                if c.get("domain") in ("post_tag", "portfolio_tags")]
        fm = {
            "title": html.unescape(text(item, "title")),
            "date": iso(text(item, "wp:post_date_gmt")),
            "lastmod": iso(text(item, "wp:post_modified_gmt")),
            "slug": slug,
            # WordPress excerpts here just repeat the first paragraph (PaperMod would show it twice),
            # so only an explicit SEO description is kept; Hugo builds summaries on its own.
            "description": plain_summary(postmeta(item, "_yoast_wpseo_metadesc")),
            "categories": [c for c in cats if c != "Uncategorized"],
            "tags": tags,
        }
        if ptype == "page":
            fm.pop("date"), fm.pop("lastmod")
            fm["comments"] = False
            fm["aliases"] = ["/contact/"]
            dest = SITE / "content" / f"{slug}.md"
        else:
            dest = SITE / "content" / ("posts" if ptype == "post" else "portfolio") / f"{slug}.md"

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(front_matter(fm) + to_markdown(text(item, "content:encoded")), encoding="utf-8")
        written.append(dest.relative_to(ROOT))

        url_path = {"post": f"/{slug}/", "portfolio": f"/portfolio/{slug}/", "page": f"/{slug}/"}[ptype]
        qkey = "page_id" if ptype == "page" else "p"
        redirects.append((qkey, pid, url_path))

        comments = []
        for c in item.findall("wp:comment", NS):
            if text(c, "wp:comment_approved") != "1" or text(c, "wp:comment_type") not in ("", "comment"):
                continue
            comments.append(c)
        if comments:
            comment_items.append((BASE_URL + url_path, comments))

    # Comments for Remark42 (names and text only: no emails or IPs, since this file is committed).
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:wp="http://wordpress.org/export/1.2/"><channel>']
    total = 0
    for link, comments in comment_items:
        out.append(f"<item><link>{html.escape(link)}</link>")
        for c in comments:
            body = text(c, "wp:comment_content").replace("]]>", "]]]]><![CDATA[>")
            out.append(
                "<wp:comment>"
                f"<wp:comment_id>{text(c, 'wp:comment_id')}</wp:comment_id>"
                f"<wp:comment_author><![CDATA[{text(c, 'wp:comment_author')}]]></wp:comment_author>"
                f"<wp:comment_date_gmt>{text(c, 'wp:comment_date_gmt')}</wp:comment_date_gmt>"
                f"<wp:comment_content><![CDATA[{body}]]></wp:comment_content>"
                "<wp:comment_approved>1</wp:comment_approved>"
                f"<wp:comment_parent>{text(c, 'wp:comment_parent') or '0'}</wp:comment_parent>"
                "</wp:comment>")
            total += 1
        out.append("</item>")
    out.append("</channel></rss>\n")
    (ROOT / "migration" / "comments-import.xml").write_text("\n".join(out), encoding="utf-8")

    # Old WordPress URLs -> new locations (imported by the Caddyfile).
    caddy = ["# Generated by migration/wp2hugo.py - redirects for old WordPress URLs.",
             "redir /feed /index.xml permanent",
             "redir /feed/ /index.xml permanent",
             "redir /comments/feed/ / permanent",
             "redir /projects/ /portfolio/ permanent",
             "redir /life-outside-work/ /about-me/ permanent",
             "redir /archives-alternate/ /archives/ permanent",
             ""]
    for qkey, pid, path in redirects:
        caddy.append(f"@wp_{qkey}_{pid} query {qkey}={pid}")
        caddy.append(f"redir @wp_{qkey}_{pid} {path} permanent")
    dest = ROOT / "deploy" / "caddy" / "wp-redirects.caddy"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(caddy) + "\n", encoding="utf-8")

    print(f"wrote {len(written)} content files, {total} comments on {len(comment_items)} pages, "
          f"{len(redirects)} ?p= redirects, {len(media)} media references")
    if args.fetch_media:
        fetch_media()


if __name__ == "__main__":
    main()
