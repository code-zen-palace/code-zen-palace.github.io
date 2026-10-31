#!/usr/bin/env python3
"""Build the PrimeKamp website (primekampllc.com) from src/ into the repo root.

    python3 tools/build.py           write every page
    python3 tools/build.py --check   exit 1 if a committed page is out of date

Python 3 standard library only. The pages are plain HTML committed next to
their sources, so GitHub Pages serves the files exactly as they are.

    src/site.json         company details, navigation, share image
    src/products.json     every product: games, TravelCharika, anything later
    src/templates/        base.html: the <head>, header and footer of each page
    src/pages/            hand-written pages, with front matter between --- lines
    src/legal/<id>/       each product's legal pages, kept word for word

Product pages, cards, the games list and the legal hub are rendered from
products.json, so a new product is one entry there (see README.md).
"""

import hashlib
import html
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

KINDS = {"game", "travel", "other"}
# live: on sale, link shown. review: waiting for the store, no link yet.
# testing: a public test listing, link shown. coming: being made.
STATUSES = {"live", "review", "testing", "coming"}
LINKED = {"live", "testing"}
LEGAL_DOCS = [
    ("privacy", "Privacy policy"),
    ("terms", "Terms of use"),
    ("delete_data", "Delete my data"),
]
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
# A product's "update": something coming in its next update ("next") or
# just out ("new"). Changing that one status changes every line below.
UPDATE_WORDS = {
    "next": {
        "badge": "In the next update",
        "chip": "{name}: in the next update",
        "line": "{name} arrives in the next update: {summary}.",
        "alt": " {name} arrives in the next update.",
    },
    "new": {
        "badge": "New",
        "chip": "New: {name}",
        "line": "New: {name}. {Summary}.",
        "alt": "",
    },
}


class BuildError(Exception):
    pass


def esc(text):
    return html.escape(str(text), quote=True)


def load_json(name):
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def read_page(path):
    """Split a source page into its front matter (a dict) and its body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise BuildError(f"{path.relative_to(ROOT)}: no front matter")
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            raise BuildError(f"{path.relative_to(ROOT)}: bad front matter line {line!r}")
        meta[key.strip()] = value.strip()
    for key in ("title", "path"):
        if key not in meta:
            raise BuildError(f"{path.relative_to(ROOT)}: front matter needs {key}")
    return meta, body


def fill(text, values, where):
    """Replace {{name}} with values[name]; an unknown name is an error."""

    def sub(match):
        key = match.group(1)
        if key not in values:
            raise BuildError(f"{where}: no value for {{{{{key}}}}}")
        return values[key]

    return PLACEHOLDER.sub(sub, text)


def out_file(path):
    """/ -> index.html, /about/ -> about/index.html, /x.html -> x.html."""
    rel = path.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return ROOT / rel


def image_size(path):
    """(width, height) of a PNG or JPEG file."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return width, height
            i += 2 + length
    raise BuildError(f"{path.relative_to(ROOT)}: not a PNG or JPEG")


def local_file(url, where):
    if not url.startswith("/"):
        raise BuildError(f"{where}: {url} must start with /")
    path = ROOT / url.lstrip("/")
    if not path.is_file():
        raise BuildError(f"{where}: {url} does not exist")
    return path


# ---------------------------------------------------------------- products


def check_products(products):
    seen = set()
    for p in products:
        where = f"products.json {p.get('id', '?')}"
        for key in ("id", "name", "kind", "page", "pitch", "description", "icon", "channels"):
            if not p.get(key):
                raise BuildError(f"{where}: needs {key}")
        if p["id"] in seen:
            raise BuildError(f"{where}: id used twice")
        seen.add(p["id"])
        if p["kind"] not in KINDS:
            raise BuildError(f"{where}: kind must be one of {sorted(KINDS)}")
        if not (p["page"].startswith("/") and p["page"].endswith("/")):
            raise BuildError(f"{where}: page must look like /name/")
        local_file(p["icon"], where)
        if "share_image" in p:
            local_file(p["share_image"].get("src", ""), where)
            if not p["share_image"].get("alt"):
                raise BuildError(f"{where}: share_image needs alt text")
        for shot in p.get("screenshots", []):
            local_file(shot["src"], where)
            if not shot.get("alt"):
                raise BuildError(f"{where}: screenshot {shot['src']} needs alt text")
            if shot.get("update") and "update" not in p:
                raise BuildError(f"{where}: screenshot {shot['src']} is marked update, but there is no update")
        if "update" in p:
            u = p["update"]
            if u.get("status") not in UPDATE_WORDS:
                raise BuildError(f"{where}: update status must be one of {sorted(UPDATE_WORDS)}")
            for key in ("name", "summary", "text"):
                if not u.get(key):
                    raise BuildError(f"{where}: update needs {key}")
        for c in p["channels"]:
            if c.get("status") not in STATUSES:
                raise BuildError(f"{where}: channel status must be one of {sorted(STATUSES)}")
            for key in ("store", "platform"):
                if not c.get(key):
                    raise BuildError(f"{where}: each channel needs {key}")
            if c["status"] in LINKED and not c.get("url"):
                raise BuildError(f"{where}: a {c['status']} channel needs a url")


def channel_label(c):
    if c.get("label"):
        return c["label"]
    return {
        "live": f"On {c['store']}",
        "review": f"Coming soon to {c['store']}",
        "testing": f"In testing on {c['store']}",
        "coming": f"{c['platform']}: coming",
    }[c["status"]]


def channel_cta(c):
    if c.get("cta"):
        return c["cta"]
    if c["status"] == "live":
        return f"Get it on {c['store']}"
    return f"{c['platform']} app on {c['store']} (in testing)"


def update_words(p, key):
    """The product's update in words: badge, chip, line or alt (see UPDATE_WORDS)."""
    u = p["update"]
    summary = u["summary"]
    return UPDATE_WORDS[u["status"]][key].format(
        name=u["name"], summary=summary, Summary=summary[:1].upper() + summary[1:]
    )


def status_spans(p):
    spans = [
        f'<span class="status status--{c["status"]}">{esc(channel_label(c))}</span>'
        for c in p["channels"]
    ]
    if "update" in p:
        spans.append(
            f'<span class="status status--{p["update"]["status"]}">{esc(update_words(p, "chip"))}</span>'
        )
    return " ".join(spans)


def product_card(p):
    return f"""      <li class="card">
        <div class="card__media"><img src="{esc(p['icon'])}" alt="" width="88" height="88"></div>
        <h3 class="card__title"><a class="card__link" href="{esc(p['page'])}">{esc(p['name'])}</a></h3>
        <p class="card__pitch">{esc(p['pitch'])}</p>
        <p class="card__meta">{status_spans(p)}</p>
      </li>"""


def more_card(more):
    if not more:
        return ""
    return f"""
      <li class="card card--more">
        <div class="card__media"><span class="spark" aria-hidden="true"><i></i><i></i><i></i></span></div>
        <h3 class="card__title">{esc(more['title'])}</h3>
        <p class="card__pitch">{esc(more['text'])}</p>
      </li>"""


def game_row(p):
    links = [f'<a class="text-link" href="{esc(p["page"])}">About {esc(p["name"])}</a>']
    for c in p["channels"]:
        if c["status"] in LINKED:
            links.append(f'<a class="text-link" href="{esc(c["url"])}">{esc(channel_cta(c))}</a>')
    update_line = ""
    if "update" in p:
        update_line = f"\n          <p>{esc(update_words(p, 'line'))}</p>"
    return f"""      <li class="pk-card game-row">
        <img class="app-icon" src="{esc(p['icon'])}" alt="" width="96" height="96">
        <div class="game-row__body">
          <h2><a href="{esc(p['page'])}">{esc(p['name'])}</a></h2>
          <p class="game-row__pitch">{esc(p['pitch'])}</p>
          <p>{esc(p['description'])}</p>{update_line}
          <p class="card__meta">{status_spans(p)}</p>
          <p class="link-row">{' '.join(links)}</p>
        </div>
      </li>"""


def more_row(more):
    if not more:
        return ""
    return f"""
      <li class="pk-card game-row game-row--more">
        <span class="spark spark--icon" aria-hidden="true"><i></i><i></i><i></i></span>
        <div class="game-row__body">
          <h2>{esc(more['title'])}</h2>
          <p>{esc(more['text'])}</p>
        </div>
      </li>"""


def legal_links(p, current=None, indent="        "):
    items = []
    for key, label in LEGAL_DOCS:
        url = p.get("legal", {}).get(key)
        if not url:
            continue
        mark = ' aria-current="page"' if url == current else ""
        items.append(f'{indent}<li><a href="{esc(url)}"{mark}>{label}</a></li>')
    return "\n".join(items)


def is_external(url):
    return url.startswith("http://") or url.startswith("https://")


def legal_item(p):
    urls = [u for u in p.get("legal", {}).values()]
    note = ""
    if urls and all(is_external(u) for u in urls):
        host = re.sub(r"^https?://([^/]+).*$", r"\1", urls[0])
        note = f'\n        <p class="small">These pages live on {esc(host)}.</p>'
    help_line = ""
    if p.get("support_email"):
        mail = esc(p["support_email"])
        help_line = f'\n        <p class="small">Questions about your data: <a href="mailto:{mail}">{mail}</a></p>'
    return f"""      <li class="pk-card legal-item">
        <h2 class="legal-item__name"><img src="{esc(p['icon'])}" alt="" width="40" height="40">{esc(p['name'])}</h2>
        <ul class="legal-links">
{legal_links(p, indent="          ")}
        </ul>{note}{help_line}
      </li>"""


def product_page(p, site):
    if p["kind"] == "game":
        eyebrow = '<a href="/games/">Games</a>'
        nav = "/games/"
    else:
        eyebrow = "Travel" if p["kind"] == "travel" else "Product"
        nav = p["page"]

    linked = [c for c in p["channels"] if c["status"] in LINKED]
    primary = next((c for c in linked if c["status"] == "live"), None)
    actions = []
    if primary:
        actions.append(f'<a class="pk-button" href="{esc(primary["url"])}">{esc(channel_cta(primary))}</a>')
    for c in linked:
        if c is not primary:
            actions.append(f'<a class="text-link" href="{esc(c["url"])}">{esc(channel_cta(c))}</a>')
    actions_html = ""
    if actions:
        actions_html = '\n      <div class="actions">\n        ' + "\n        ".join(actions) + "\n      </div>"

    store_name = ""
    if p.get("store_title") and p["store_title"] != p["name"]:
        store_name = f'\n      <p class="small">Its name on Google Play: <strong>{esc(p["store_title"])}</strong></p>'

    shots = ""
    if p.get("screenshots"):
        items = []
        for shot in p["screenshots"]:
            w, h = image_size(local_file(shot["src"], p["id"]))
            alt, note = shot["alt"], ""
            # A picture of the update says so: in its alt text, and in a
            # line under it that screen readers skip (the alt has it).
            if shot.get("update"):
                alt += update_words(p, "alt")
                note = f'<p class="shot-note" aria-hidden="true">{esc(update_words(p, "chip"))}</p>'
            items.append(
                f'      <li><img src="{esc(shot["src"])}" alt="{esc(alt)}" '
                f'width="{w}" height="{h}" loading="lazy">{note}</li>'
            )
        shots = f"""
<section class="section section--tight" aria-label="Screenshots">
  <div class="wrap">
    <ul class="shots">
{chr(10).join(items)}
    </ul>
  </div>
</section>
"""

    update_html = ""
    if "update" in p:
        u = p["update"]
        anchor = re.sub(r"[^a-z0-9]+", "-", u["name"].lower()).strip("-")
        update_html = f"""
<section class="section section--tight" aria-labelledby="{anchor}">
  <div class="wrap">
    <div class="pk-card panel update">
      <p class="card__meta"><span class="status status--{u['status']}">{esc(update_words(p, 'badge'))}</span></p>
      <h2 id="{anchor}">{esc(u['name'])}</h2>
      <p>{esc(u['text'])}</p>
    </div>
  </div>
</section>
"""

    features = "\n".join(f"        <li>{esc(f)}</li>" for f in p.get("features", []))
    money = p.get("money")
    money_html = ""
    if money:
        money_html = f"""
    <div class="pk-card panel">
      <h2>{esc(money['title'])}</h2>
      <p>{esc(money['text'])}</p>
    </div>"""

    help_items = legal_links(p)
    if p.get("support_email"):
        mail = esc(p["support_email"])
        help_items += f'\n        <li><a href="mailto:{mail}">Email {mail}</a></li>'

    body = f"""<section class="page-head product-head">
  <div class="wrap">
    <p class="eyebrow">{eyebrow}</p>
    <div class="product-head__title">
      <img class="app-icon app-icon--large" src="{esc(p['icon'])}" alt="" width="112" height="112">
      <div>
        <h1>{esc(p['name'])}</h1>
        <p class="lead">{esc(p['pitch'])}</p>
      </div>
    </div>
    <div class="product-head__about">
      <p>{esc(p['description'])}</p>
      <p class="card__meta">{status_spans(p)}</p>{store_name}{actions_html}
    </div>
  </div>
</section>
{shots}{update_html}
<section class="section section--tight">
  <div class="wrap duo">
    <div class="pk-card panel">
      <h2>What it's like</h2>
      <ul class="pixel-list">
{features}
      </ul>
    </div>{money_html}
  </div>
</section>

<section class="section section--tight">
  <div class="wrap">
    <div class="pk-card panel">
      <h2>Help and legal</h2>
      <ul class="legal-links">
{help_items}
      </ul>
    </div>
  </div>
</section>
"""
    meta = {
        "title": f"{p['name']} · {p['pitch'].rstrip('.')}",
        "description": f"{p['name']}: {p['pitch']} {p['description']}"
        + (f" {update_words(p, 'line')}" if "update" in p else ""),
        "path": p["page"],
        "nav": nav,
    }
    if p.get("share_image"):
        meta["share_image"] = p["share_image"]
    return meta, body


# ------------------------------------------------------------------- pages


def company_address(site):
    a = site["address"]
    mail = esc(site["email"])
    tel = esc("+" + "".join(c for c in site["phone"] if c.isdigit()))
    return f"""      <address class="company">
        <p><strong>{esc(site['legal_name'])}</strong><br>
        {esc(site['registration'])}</p>
        <p>{esc(a['street'])}<br>
        {esc(a['city'])}, {esc(a['region'])} {esc(a['postal_code'])}, {esc(a['country'])}</p>
        <p><a href="mailto:{mail}">{mail}</a><br>
        <a href="tel:{tel}">{esc(site['phone'])}</a></p>
      </address>"""


def support_list(products):
    by_mail = {}
    for p in products:
        if p.get("support_email"):
            by_mail.setdefault(p["support_email"], []).append(p["name"])
    lines = []
    for mail, names in by_mail.items():
        if len(names) > 1:
            names_text = ", ".join(names[:-1]) + " or " + names[-1]
        else:
            names_text = names[0]
        m = esc(mail)
        lines.append(
            f"      <p>For help with {esc(names_text)}, or a question about your data in them, "
            f'write to <a href="mailto:{m}">{m}</a>.</p>'
        )
    lines.append('      <p>Each game\'s privacy policy says what it collects: see <a href="/legal/">Privacy and terms</a>.</p>')
    return "\n".join(lines)


def organization_json(site):
    a = site["address"]
    data = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site["legal_name"],
        "alternateName": site["name"],
        "url": site["base_url"] + "/",
        "logo": site["base_url"] + "/android-chrome-512x512.png",
        "email": site["email"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": a["street"],
            "addressLocality": a["city"],
            "addressRegion": a["region"],
            "postalCode": a["postal_code"],
            "addressCountry": a["country_code"],
        },
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>\n"


def nav_html(items, path, section, indent):
    """aria-current="page" on the link to this page; "true" on its section."""
    lines = []
    for item in items:
        mark = ""
        if item["href"] == path:
            mark = ' aria-current="page"'
        elif item["href"] == section:
            mark = ' aria-current="true"'
        lines.append(f'{indent}<li><a href="{esc(item["href"])}"{mark}>{esc(item["label"])}</a></li>')
    return "\n".join(lines)


def render(base, site, meta, body, css_version, extra_head=""):
    light = meta.get("theme") == "light"
    path = meta["path"]
    section = meta.get("nav", path)
    canonical = site["base_url"] + path
    # The link-preview picture: a product's own, or the company's.
    share = meta.get("share_image") or {"src": site["share_image"], "alt": site["share_image_alt"]}
    width, height = image_size(local_file(share["src"], path))
    return fill(
        base,
        {
            "html_theme": ' data-theme="light"' if light else "",
            "title": esc(meta["title"]),
            "description": esc(meta.get("description", "")),
            "canonical": esc(canonical),
            "share_image": esc(site["base_url"] + share["src"]),
            "share_image_alt": esc(share["alt"]),
            "share_image_width": str(width),
            "share_image_height": str(height),
            "css_version": css_version,
            "extra_head": extra_head,
            "header_logo": "/assets/logo/primekamp_horizontal_on-light.svg"
            if light
            else "/assets/logo/primekamp_horizontal_on-dark.svg",
            "nav": nav_html(site["nav"], path, section, "        "),
            "footer_nav": nav_html(site["footer_nav"], path, section, "        "),
            "body": body.rstrip("\n"),
            "copyright": esc(site["copyright"]),
        },
        meta["path"],
    )


def build():
    """Return {output path: html} for every generated file."""
    site = load_json("site.json")
    data = load_json("products.json")
    products = data["products"]
    check_products(products)
    by_id = {p["id"]: p for p in products}
    base = (SRC / "templates" / "base.html").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "site.css").read_bytes()
    css_version = hashlib.sha1(css).hexdigest()[:10]
    more = data.get("more_card")
    games = [p for p in products if p["kind"] == "game"]

    shared = {
        "product_cards": "\n".join(product_card(p) for p in products) + more_card(more),
        "game_rows": "\n".join(game_row(p) for p in games) + more_row(more),
        "legal_list": "\n".join(legal_item(p) for p in products if p.get("legal")),
        "company_address": company_address(site),
        "support_list": support_list(products),
        "email": esc(site["email"]),
    }

    pages = {}
    sitemap = []

    def add(meta, body, extra_head=""):
        target = out_file(meta["path"])
        if target in pages:
            raise BuildError(f"two pages write {meta['path']}")
        pages[target] = render(base, site, meta, body, css_version, extra_head)
        if meta["path"] != "/404.html":
            sitemap.append(site["base_url"] + meta["path"])

    for src in sorted((SRC / "pages").glob("*.html")):
        meta, body = read_page(src)
        body = fill(body, shared, str(src.relative_to(ROOT)))
        extra = organization_json(site) if meta["path"] == "/" else ""
        add(meta, body, extra)

    for p in products:
        meta, body = product_page(p, site)
        add(meta, body)

    # Legal pages: the article is copied as it is; only the page around it is new.
    for src in sorted((SRC / "legal").glob("*/*.html")):
        meta, article = read_page(src)
        p = by_id.get(meta.get("product"))
        if not p:
            raise BuildError(f"{src.relative_to(ROOT)}: unknown product {meta.get('product')!r}")
        if p.get("legal", {}).get(meta.get("doc")) != meta["path"]:
            raise BuildError(f"{src.relative_to(ROOT)}: products.json does not link {meta['path']}")
        body = f"""<div class="wrap doc-page">
  <nav class="doc-nav" aria-label="{esc(p['name'])} legal pages">
    <a class="doc-nav__product" href="{esc(p['page'])}"><img src="{esc(p['icon'])}" alt="" width="32" height="32">{esc(p['name'])}</a>
    <ul>
{legal_links(p, meta['path'], "      ")}
    </ul>
  </nav>
  <article class="doc">
{article}</article>
</div>"""
        about = {
            "privacy": f"How {p['name']} handles your information, and your choices.",
            "terms": f"The terms of use for {p['name']}.",
            "delete_data": f"How to delete your {p['name']} data.",
        }
        meta = {
            "title": meta["title"],
            "description": meta.get("description", about.get(meta.get("doc"), meta["title"])),
            "path": meta["path"],
            "nav": "/legal/",
            "theme": "light",
        }
        add(meta, body)

    urls = "\n".join(f"  <url><loc>{esc(u)}</loc></url>" for u in sorted(sitemap))
    pages[ROOT / "sitemap.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n"
    )
    pages[ROOT / "robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {site['base_url']}/sitemap.xml\n"
    return pages


def main(argv):
    check = "--check" in argv
    try:
        pages = build()
    except BuildError as error:
        print(f"build: {error}", file=sys.stderr)
        return 2
    stale = []
    for target, text in sorted(pages.items()):
        old = target.read_text(encoding="utf-8") if target.exists() else None
        if old == text:
            continue
        stale.append(target.relative_to(ROOT))
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    if check:
        for path in stale:
            print(f"out of date: {path}")
        return 1 if stale else 0
    for path in stale:
        print(f"wrote {path}")
    print(f"{len(pages)} files, {len(stale)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
