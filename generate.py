"""PostielkyPostele.sk - ramiky pre katalogove reklamy na Mete.

Stiahne produktovy feed z e-shopu, ku kazdemu produktu nakresli obrazok
1080x1080 s ramikom (logo, cena, kod zlavy, Snivko, vyhody) a vytvori
doplnkovy feed (id, image_link) pre katalog v Meta Commerce Manageri.
E-shop sa nemeni - menia sa len obrazky v reklamach.

Spustenie:  python generate.py [--limit N] [--only ID,ID]
Vystup:     site/img/<id>.jpg, site/feed.csv, site/index.html
"""
import argparse, csv, datetime as dt, io, json, re, sys, unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
A = ROOT / "assets"
OUT = ROOT / "site"
NS = {"g": "http://base.google.com/ns/1.0"}
W = H = 1080

ORANGE = (255, 122, 0)
RED = (227, 6, 19)
INK = (29, 36, 51)
CREAM = (251, 246, 238)
GREY = (138, 132, 120)
GREEN = (31, 157, 85)


def font(weight, size):
    return ImageFont.truetype(str(A / f"Nunito-{weight}.ttf"), size)


def norm(s):
    s = (s or "").replace("×", "x")
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


def money(s):
    if not s:
        return None
    m = re.search(r"([\d\s]+[.,]?\d*)", s)
    return float(m.group(1).replace(" ", "").replace(",", ".")) if m else None


def fmt(v):
    return (f"{v:.0f}" if abs(v - round(v)) < 0.005 else f"{v:.2f}".replace(".", ",")) + " €"


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 katalog-ramiky"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def matches(rule, text, title):
    if not all(w in text for w in rule["obsahuje"]):
        return False
    if "min_sirka" in rule:
        m = re.search(r"(\d{2,3})\s*[x×]\s*200", title or "")
        if not m or int(m.group(1)) < rule["min_sirka"]:
            return False
    return True


def promo_for(cfg, text, title):
    a = cfg["akcia"]
    if not a.get("aktivna"):
        return None
    today = dt.date.today().isoformat()
    if not (a["od"] <= today <= a["do"]):
        return None
    for r in a["pravidla"]:
        if matches(r, text, title):
            return r
    return None


def chips_for(cfg, text, price, in_stock):
    out = [v["text"] for v in cfg["vyhody"] if all(w in text for w in v["obsahuje"])][:1]
    if in_stock:
        out.append("skladom")
    if price is not None and price >= cfg["doprava_zadarmo_od"]:
        out.append("doprava zadarmo")
    return out[:3]


def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def paste_contain(canvas, img, box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    img = img.convert("RGBA")
    r = min(bw / img.width, bh / img.height)
    img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))), Image.LANCZOS)
    canvas.alpha_composite(img, (x0 + (bw - img.width) // 2, y0 + (bh - img.height) // 2))


def paste_cover(canvas, img, box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    img = img.convert("RGBA")
    r = max(bw / img.width, bh / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    l, t = (img.width - bw) // 2, (img.height - bh) // 2
    canvas.alpha_composite(img.crop((l, t, l + bw, t + bh)), (x0, y0))


def shadowed(canvas, layer_fn, offset=(0, 10), blur=14, alpha=60):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer_fn(ImageDraw.Draw(sh), (0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh, offset)


def badge(canvas, code, amount):
    size = 200
    b = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.ellipse((10, 10, size + 10, size + 10), fill=(255, 255, 255, 255))
    d.ellipse((16, 16, size + 4, size + 4), fill=RED + (255,))
    f1, f2 = font(900, 62), font(900, 22)
    t1, t2 = f"−{amount} €", f"KÓD {code}"
    d.text(((size + 20 - text_w(d, t1, f1)) / 2, 58), t1, font=f1, fill="white")
    d.text(((size + 20 - text_w(d, t2, f2)) / 2, 132), t2, font=f2, fill="white")
    b = b.rotate(8, resample=Image.BICUBIC, expand=False)
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((W - 250, 40, W - 50, 240), fill=(0, 0, 0, 70))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (0, 10))
    canvas.alpha_composite(b, (W - 260, 30))


def render(cfg, p, photo, lifestyle):
    c = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(c)
    if lifestyle:
        paste_cover(c, photo, (0, 0, W, H - 250))
    else:
        paste_contain(c, photo, (60, 110, W - 60, H - 270))

    # spodny pruh
    d.rectangle((0, H - 264, W, H), fill=CREAM)

    # logo na bielom podklade
    logo = Image.open(A / "logo.png").convert("RGBA")
    lh = 62
    logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
    if lifestyle:
        d.rounded_rectangle((26, 22, 26 + logo.width + 28, 22 + lh + 24), 16, fill=(255, 255, 255, 240))
    c.alpha_composite(logo, (40, 34))

    promo = p["promo"]
    price = p["price_now"]
    x = 46
    if promo:
        final = price - promo["zlava"]
        f_old, f_new, f_em = font(800, 38), font(900, 116), font(900, 26)
        d.text((x, H - 248), fmt(price), font=f_old, fill=GREY)
        ow = text_w(d, fmt(price), f_old)
        d.line((x, H - 224, x + ow, H - 224), fill=GREY, width=4)
        d.text((x - 4, H - 214), fmt(final), font=f_new, fill=RED)
        d.text((x, H - 76), "s kódom", font=f_em, fill=INK)
        kx = x + text_w(d, "s kódom ", f_em)
        kw = text_w(d, promo["kod"], f_em)
        d.rounded_rectangle((kx - 4, H - 76, kx + kw + 14, H - 40), 8, fill=RED)
        d.text((kx + 5, H - 76), promo["kod"], font=f_em, fill="white")
        badge(c, promo["kod"], promo["zlava"])
        price_right = x + max(text_w(d, fmt(final), f_new), 220)
    else:
        f_old, f_new = font(800, 38), font(900, 116)
        if p["price_before"] and p["price_before"] > price:
            d.text((x, H - 248), fmt(p["price_before"]), font=f_old, fill=GREY)
            ow = text_w(d, fmt(p["price_before"]), f_old)
            d.line((x, H - 224, x + ow, H - 224), fill=GREY, width=4)
        d.text((x - 4, H - 200), fmt(price), font=f_new, fill=RED)
        price_right = x + text_w(d, fmt(price), f_new)

    # vyhody vpravo
    f_chip = font(800, 26)
    y = H - 230
    chips = p["chips"]
    cy = H - 40 - len(chips) * 58 + 8
    CK = 30  # sirka fajky + medzera
    for t in chips:
        tw = CK + text_w(d, t, f_chip)
        x1 = W - 40
        x0 = x1 - tw - 44
        d.rounded_rectangle((x0, cy, x1, cy + 48), 24, fill="white")
        fx, fy = x0 + 22, cy + 24
        d.line([(fx, fy), (fx + 7, fy + 8), (fx + 20, fy - 9)], fill=GREEN, width=5, joint="curve")
        d.text((x0 + 22 + CK, cy + 6), t, font=f_chip, fill=INK)
        cy += 58
    chips_left = W - 40 - max([CK + text_w(d, t, f_chip) + 44 for t in chips] or [0])

    # Snivko medzi cenou a vyhodami, ukazuje na cenu
    sn = Image.open(A / "snivko.png").convert("RGBA")
    room = chips_left - price_right - 20
    if room > 150:
        sw = min(250, room)
        sn = sn.resize((int(sw), int(sn.height * sw / sn.width)), Image.LANCZOS)
        sx = int(price_right + (room - sw) / 2 + 10)
        c.alpha_composite(sn, (sx, H - 18 - sn.height))

    # oranzovy ramik
    d.rectangle((0, 0, W - 1, H - 1), outline=ORANGE, width=14)
    return c.convert("RGB")


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        g = lambda k: (it.find(f"g:{k}", NS).text if it.find(f"g:{k}", NS) is not None else None)
        items.append({k: g(k) for k in ("id", "title", "price", "sale_price", "image_link", "availability", "product_type", "link")})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--feed-file", default="")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    xml = Path(args.feed_file).read_bytes() if args.feed_file else fetch(cfg["feed_url"], 120)
    items = parse_feed(xml)
    if args.only:
        ids = set(args.only.split(","))
        items = [i for i in items if i["id"] in ids]
    if args.limit:
        items = items[: args.limit]

    (OUT / "img").mkdir(parents=True, exist_ok=True)
    rows, errors = [], []

    def work(it):
        try:
            title = it["title"] or ""
            text = norm(title + " " + (it["product_type"] or ""))
            reg, sale = money(it["price"]), money(it["sale_price"])
            now = sale if sale and reg and sale < reg else reg
            if now is None:
                raise ValueError("chyba cena")
            in_stock = (it["availability"] or "").lower().replace("_", " ") == "in stock"
            ls_url = cfg.get("lifestyle", {}).get(it["id"])
            photo = Image.open(io.BytesIO(fetch(ls_url or it["image_link"])))
            p = {
                "price_now": now,
                "price_before": reg if sale and reg and sale < reg else None,
                "promo": promo_for(cfg, text, title),
                "chips": chips_for(cfg, text, now, in_stock),
            }
            img = render(cfg, p, photo, bool(ls_url))
            safe = re.sub(r"[^A-Za-z0-9_-]", "_", it["id"])
            img.save(OUT / "img" / f"{safe}.jpg", quality=86, optimize=True)
            return (it["id"], f'{cfg["public_base_url"]}/img/{safe}.jpg')
        except Exception as e:  # produkt preskocime, v Mete ostane povodny obrazok
            errors.append((it.get("id"), str(e)))
            return None

    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(work, items):
            if r:
                rows.append(r)

    with open(OUT / "feed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "image_link"])
        w.writerows(sorted(rows))

    stamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    sample = "".join(f'<img src="img/{re.sub(r"[^A-Za-z0-9_-]", "_", i)}.jpg" loading="lazy">' for i, _ in sorted(rows)[:60])
    (OUT / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Katalog ramiky</title>"
        f"<style>body{{font-family:sans-serif;margin:16px}}img{{width:220px;margin:4px;border:1px solid #ddd}}</style>"
        f"<h1>Katalóg rámiky</h1><p>Aktualizované {stamp} · {len(rows)} produktov · chyby: {len(errors)}</p>"
        f'<p>Doplnkový feed pre Metu: <a href="feed.csv">feed.csv</a></p>{sample}',
        encoding="utf-8",
    )
    (OUT / ".nojekyll").write_text("")
    print(f"Hotovo: {len(rows)} obrazkov, chyby: {len(errors)}")
    for e in errors[:20]:
        print("  chyba", e)


if __name__ == "__main__":
    main()
