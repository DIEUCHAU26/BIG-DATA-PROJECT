# -*- coding: utf-8 -*-
"""
crawl_all.py - Cào sản phẩm mỹ phẩm / chăm sóc cá nhân từ Cocolux và Hasaki.

CÁCH DÙNG
  pip install playwright pymongo
  playwright install chromium

  python crawl_all.py --links-only        # chỉ đếm tổng số sản phẩm mỗi danh mục (nhanh)
  python crawl_all.py --test              # chạy thử nhỏ (3 danh mục x 3 sản phẩm), xem trường nào lấy được
  python crawl_all.py                     # chạy thật, cả 2 nguồn song song
  python crawl_all.py --source cocolux    # chỉ chạy 1 nguồn

GHI CHÚ
  - Dữ liệu luôn được ghi vào thư mục data/ (file .jsonl).
  - Nếu đặt biến môi trường MONGO_URI thì ghi thêm vào MongoDB (DB: abda_cosmetics).
  - Script chạy lại được: sản phẩm đã cào (theo URL) sẽ được bỏ qua.
  - Nếu trang yêu cầu xác thực/CAPTCHA, hãy tự xử lý trong cửa sổ trình duyệt.
    Script chỉ chờ, KHÔNG tự vượt xác thực.
  - Hãy xem robots.txt và điều khoản của từng trang, và giữ tốc độ cào chậm.
"""
import argparse
import json
import os
import random
import re
import time
from datetime import datetime
from multiprocessing import Process
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("data")
DATA.mkdir(exist_ok=True)


class Blocked(Exception):
    pass


# --------------------------------------------------------------------------
# CẤU HÌNH NGUỒN VÀ DANH MỤC
# (category_group, tên danh mục, đường dẫn hoặc URL đầy đủ)
# Chỉ cần các danh mục lớn: trang danh mục lớn đã gồm các mục con.
# Mỗi sản phẩm chỉ giữ 1 bản theo URL.
# --------------------------------------------------------------------------
COCOLUX_CATEGORIES = [
    ("Chăm sóc da", "Chăm sóc da", "https://cocolux.com/danh-muc/cham-soc-da-skincare-i.105"),
    ("Trang điểm", "Son môi", "https://cocolux.com/danh-muc/son-moi-lips-i.98"),
    ("Trang điểm", "Trang điểm", "https://cocolux.com/danh-muc/trang-diem-makeup-i.83"),
    ("Trang điểm", "Mascara", "https://cocolux.com/danh-muc/mascara-i.97"),
    ("Chăm sóc tóc", "Chăm sóc tóc", "https://cocolux.com/danh-muc/cham-soc-toc-haircare-i.146"),
    ("Chăm sóc cơ thể", "Chăm sóc cơ thể", "https://cocolux.com/danh-muc/cham-soc-co-the-bodycare-i.130"),
    ("Nước hoa", "Nước hoa", "https://cocolux.com/danh-muc/nuoc-hoa-perfume-i.148"),
]

# HASAKI: mở từng mục trong menu, copy URL trên thanh địa chỉ, dán thay cho chữ DÁN_...
HASAKI_CATEGORIES = [
    ("Chăm sóc da", "Chăm sóc da mặt", "https://hasaki.vn/danh-muc/cham-soc-da-mat-c4.html"),
    ("Trang điểm", "Trang điểm", "https://hasaki.vn/danh-muc/trang-diem-c23.html"),
    ("Chăm sóc tóc", "Chăm sóc tóc và da đầu", "https://hasaki.vn/danh-muc/cham-soc-toc-c96.html"),
    ("Chăm sóc cơ thể", "Chăm sóc cơ thể", "https://hasaki.vn/danh-muc/cham-soc-co-the-c12.html"),
    ("Nước hoa", "Nước hoa", "https://hasaki.vn/danh-muc/nuoc-hoa-c103.html"),
]





CONFIG = {
    "cocolux": {
        "base": "https://cocolux.com",
        "categories": COCOLUX_CATEGORIES,
        "product_re": r"https?://(?:www\.)?cocolux\.com/[^/]+-i\.\d+/?",
    },
    "hasaki": {
        "base": "https://hasaki.vn",
        "categories": HASAKI_CATEGORIES,
        "product_re": r"https?://(?:www\.)?hasaki\.vn/san-pham/[^/]+\.html",
    },
}

BLOCK_HINTS = ("xác thực bảo mật", "captcha", "verify you are human", "access denied")
PRICE_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|₫|vnd)", re.I)
FIELDS = ["name", "brand", "product_code", "price", "price_original", "rating",
          "review_count", "sold", "origin", "skin_type", "volume", "category"]


# --------------------------------------------------------------------------
# TIỆN ÍCH
# --------------------------------------------------------------------------
def to_int(s):
    d = re.sub(r"\D", "", str(s or ""))
    return int(d) if d else None


def to_price(v):
    if v is None:
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.0+)?", s):
        return int(float(s))
    return to_int(s)


def to_float(v):
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return None


def check_blocked(page):
    """Nếu thấy trang xác thực thì chờ để bạn tự xử lý. Không tự vượt."""
    for _ in range(3):
        try:
            body = page.inner_text("body")
        except Exception:
            return
        title = (page.title() or "").lower()
        hit = any(h in title for h in BLOCK_HINTS) or (
            len(body) < 2000 and any(h in body.lower() for h in BLOCK_HINTS))
        if not hit:
            return
        print("[!] Có vẻ cần xác thực. Hãy xử lý trong cửa sổ trình duyệt, đợi 60 giây...")
        page.wait_for_timeout(60000)
    raise Blocked()


def label(text, name):
    """Lấy giá trị đứng cạnh một nhãn, ví dụ 'Loại da <tab> Da nhạy cảm'."""
    m = re.search(rf"^[ \t]*{name}[ \t]*(?:[\t|:]|\n)[ \t\n|:]*([^\n\t|]+)",
                  text, flags=re.M | re.I)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return None


def parse_sold(text):
    """'Đã bán 215' -> 215, 'Đã bán 2.9k' -> 2900."""
    m = re.search(r"Đã bán\s*([\d.,]+)\s*([kK]?)", text)
    if not m:
        return None
    num, k = m.group(1), m.group(2)
    if k:
        try:
            return int(round(float(num.replace(",", ".")) * 1000))
        except Exception:
            return None
    return to_int(num)


def parse_volume(name):
    m = re.findall(r"(\d+(?:[.,]\d+)?)\s*(ml|gr|g|l|kg)\b", name or "", flags=re.I)
    return f"{m[-1][0]}{m[-1][1].lower()}" if m else None


def read_jsonld_product(page):
    try:
        blocks = page.eval_on_selector_all(
            'script[type="application/ld+json"]', "els => els.map(e => e.textContent)")
    except Exception:
        return {}
    for s in blocks:
        try:
            data = json.loads(s)
        except Exception:
            continue
        if isinstance(data, dict):
            items = data.get("@graph", [data])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for it in items:
            if isinstance(it, dict):
                t = it.get("@type")
                if t == "Product" or (isinstance(t, list) and "Product" in t):
                    return it
    return {}


# --------------------------------------------------------------------------
# LẤY DANH SÁCH LINK SẢN PHẨM TRONG MỘT DANH MỤC
# --------------------------------------------------------------------------
NEXT_TEXTS = ("sau", "tiếp", "trang sau", "tiếp theo", ">", "»", "›", "next")


def go_next_page(page, page_no):
    """Tìm nút / liên kết sang trang kế tiếp (nút 'Sau', '>', số trang kế...)."""
    try:
        items = page.eval_on_selector_all(
            "a, button",
            "els => els.map((e, i) => ({i: i, t: (e.innerText || '').trim(), "
            "r: e.getAttribute('rel') || ''}))")
    except Exception:
        return False
    for it in items:
        t = it["t"].lower()
        if it["r"] == "next" or t in NEXT_TEXTS or t == str(page_no + 1):
            try:
                el = page.locator("a, button").nth(it["i"])
                if not el.is_visible():
                    continue
                el.scroll_into_view_if_needed(timeout=2000)
                el.click(timeout=3000)
                page.wait_for_timeout(2500)
                return True
            except Exception:
                continue
    return False


LAST_INFO = {}
SKIP_PATHS = ("/danh-muc/", "/blog/", "/thuong-hieu/", "/cam-nang/", "/tin-tuc/", "/campaign/")
LOOSE_RE = re.compile(r"https?://[^/]+/[^?#]*(?:-i\.\d+|\.html)/?")


def looks_odd(h):
    """Link GIỐNG link sản phẩm nhưng không khớp mẫu chuẩn (để báo cáo, không tự thêm)."""
    return (not any(x in h for x in SKIP_PATHS)) and LOOSE_RE.fullmatch(h) is not None


def read_web_total(page):
    """Đọc số 'N kết quả' (hoặc 'N sản phẩm') mà trang tự hiển thị."""
    try:
        text = page.inner_text("body")
    except Exception:
        return None
    m = re.search(r"(\d[\d.,]*)\s*kết quả", text, re.I) or \
        re.search(r"(\d[\d.,]*)\s*sản phẩm", text, re.I)
    return to_int(m.group(1)) if m else None


def count_product_links(page, product_re):
    try:
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    except Exception:
        return 0
    return len({h.split("#")[0].split("?")[0] for h in hrefs
                if re.fullmatch(product_re, h.split("#")[0].split("?")[0])})


def click_load_more(page, product_re):
    """Bấm nút 'Xem thêm' làm HIỆN THÊM sản phẩm.
    Trang có thể có nhiều nút 'Xem thêm' (ví dụ phần mô tả SEO), nên thử từng nút
    và chỉ giữ nút nào làm tăng số sản phẩm."""
    btns = page.get_by_text(
        re.compile(r"^\s*(xem thêm|tải thêm|hiển thị thêm)[^\n]{0,25}$", re.I))
    try:
        n = btns.count()
    except Exception:
        return False
    before = count_product_links(page, product_re)
    for i in range(n - 1, -1, -1):
        try:
            b = btns.nth(i)
            if not b.is_visible():
                continue
            b.scroll_into_view_if_needed(timeout=2000)
            b.click(timeout=2000)
            page.wait_for_timeout(2000)
            if count_product_links(page, product_re) > before:
                return True
        except Exception:
            continue
    return False


def collect_by_url_param(page, url, product_re, links, max_n):
    """Thử chuyển trang bằng tham số trên URL (?p=2, ?page=2...).
    Chỉ chấp nhận cách nào cho ra link sản phẩm MỚI."""
    sep = "&" if "?" in url else "?"
    tag = url.rstrip("/").split("/")[-1][:35]
    for param in ("p", "page", "pageIndex", "pageNumber", "trang"):
        n, found_any = 2, False
        while n < 1000:
            page.goto(f"{url}{sep}{param}={n}", wait_until="domcontentloaded", timeout=60000)
            check_blocked(page)
            page.wait_for_timeout(2500)
            for _ in range(3):
                page.mouse.wheel(0, 5000)
                page.wait_for_timeout(1000)
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            found = {h.split("#")[0].split("?")[0] for h in hrefs}
            new = {h for h in found if re.fullmatch(product_re, h)} - links
            if not new:
                break
            links.update(new)
            found_any = True
            print(f"  ... [{tag}] {param}={n}: tổng {len(links)} link")
            if max_n and len(links) >= max_n:
                return True
            n += 1
        if found_any:
            return True
    return False


def collect_links(page, url, product_re, max_n):
    """Lấy hết link sản phẩm của 1 danh mục: cuộn trang, bấm 'Xem thêm',
    và chuyển qua các trang kế tiếp (nếu trang chia số trang)."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    check_blocked(page)
    page.wait_for_timeout(3000)
    web_total = read_web_total(page)
    odd = set()
    links, stagnant, page_no, empty_pages, page_start = set(), 0, 1, 0, 0
    for _ in range(3000):
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        before = len(links)
        for h in hrefs:
            h = h.split("#")[0].split("?")[0]
            if re.fullmatch(product_re, h):
                links.add(h)
            elif looks_odd(h):
                odd.add(h)
        if len(links) // 100 > before // 100:
            print(f"  ... [{url.rstrip('/').split('/')[-1][:35]}] đã có {len(links)} link (trang {page_no})")
        if max_n and len(links) >= max_n:
            break
        page.mouse.wheel(0, 5000)
        click_load_more(page, product_re)
        page.wait_for_timeout(1500)
        stagnant = stagnant + 1 if len(links) == before else 0
        if stagnant >= 6:
            empty_pages = empty_pages + 1 if len(links) == page_start else 0
            if empty_pages >= 2 or not go_next_page(page, page_no):
                break
            page_no += 1
            page_start = len(links)
            stagnant = 0
            check_blocked(page)
            print(f"  ... [{url.rstrip('/').split('/')[-1][:35]}] sang trang {page_no}, đã có {len(links)} link")
    if page_no == 1 and not max_n:
        # quét lần cuối cho chắc: cuộn hết cỡ, bấm "Xem thêm" thêm vài lần
        for _ in range(3):
            page.mouse.wheel(0, 8000)
            page.wait_for_timeout(2000)
            click_load_more(page, product_re)
            page.wait_for_timeout(1500)
            for h in page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"):
                h = h.split("#")[0].split("?")[0]
                if re.fullmatch(product_re, h):
                    links.add(h)
    if page_no == 1 and not (max_n and len(links) >= max_n):
        collect_by_url_param(page, url, product_re, links, max_n)
    LAST_INFO.update(web_total=web_total, odd=sorted(odd - links))
    out = list(links)
    return out[:max_n] if max_n else out


# --------------------------------------------------------------------------
# ĐỌC MỘT TRANG SẢN PHẨM
# --------------------------------------------------------------------------
def parse_product(page, url, source, group, cat):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    check_blocked(page)
    page.wait_for_timeout(2500)
    text = page.inner_text("body")
    ld = read_jsonld_product(page)

    # tên
    name = ld.get("name")
    if not name:
        try:
            name = page.locator("h1").first.inner_text().strip()
        except Exception:
            name = None

    # thương hiệu
    brand = ld.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    if not brand:
        brand = label(text, "Thương hiệu")
    if not brand:
        try:
            brand = page.locator('a[href*="/thuong-hieu/"]').first.inner_text().strip()
        except Exception:
            brand = None

    # mã sản phẩm / barcode
    code = None
    m = re.search(r"Mã sản phẩm:\s*(\d+)", text)
    if m:
        code = m.group(1)
    if not code:
        code = label(text, "Barcode")
    if not code:
        code = ld.get("gtin13") or ld.get("gtin") or ld.get("sku")

    # giá
    offers = ld.get("offers")
    if isinstance(offers, list) and offers:
        offers = offers[0]
    price = to_price(offers.get("price")) if isinstance(offers, dict) else None
    start = text.find(name) if name else 0
    prices = [to_int(p) for p in PRICE_RE.findall(text[max(start, 0):])][:6]
    if price is None and prices:
        price = prices[0]
    price_original = next((p for p in prices[1:] if price and p > price), None)
    discount_pct = (round((1 - price / price_original) * 100)
                    if price and price_original else None)

    # đánh giá
    agg = ld.get("aggregateRating") or {}
    rating = to_float(agg.get("ratingValue")) if agg else None
    # Số đánh giá: ưu tiên số hiển thị trên trang (lấy số lớn nhất),
    # vì reviewCount trong JSON-LD có thể chỉ là số review mẫu (ví dụ 5).
    nums = [to_int(x) for x in
            re.findall(r"(\d[\d.,]*)\s*(?:đánh giá|nhận xét)", text, flags=re.I)]
    nums = [n for n in nums if n is not None]
    review_count = max(nums) if nums else None
    if review_count is None and agg:
        review_count = to_int(agg.get("reviewCount"))
    if rating is None:
        m = re.search(r"(\d(?:[.,]\d)?)\s*\n?\s*\(\d[\d.,]*\s*đánh giá\)", text)
        rating = to_float(m.group(1)) if m else None

    in_stock = None
    if "Hết hàng" in text:
        in_stock = False
    elif "Còn hàng" in text:
        in_stock = True

    rec = {
        "source": source,
        "category_group": group,
        "category": cat,
        "url": url,
        "name": name,
        "brand": brand,
        "product_code": code,
        "price": price,
        "price_original": price_original,
        "discount_pct": discount_pct,
        "rating": rating,
        "review_count": review_count,
        "in_stock": in_stock,
        "sold": parse_sold(text),
        "volume": parse_volume(name),
        "origin": label(text, "Xuất xứ thương hiệu") or label(text, "Xuất xứ"),
        "skin_type": label(text, "Loại da"),
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
    }
    rec["required_ok"] = all(rec.get(k) for k in
                             ("name", "brand", "product_code", "price", "url", "category"))
    return rec


# --------------------------------------------------------------------------
# LƯU DỮ LIỆU
# --------------------------------------------------------------------------
def load_seen(path):
    seen = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["url"])
                except Exception:
                    pass
    return seen


def coverage(path):
    if not path.exists():
        return
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not rows:
        return
    print(f"\n=== {path.name}: {len(rows)} sản phẩm ===")
    for f in FIELDS:
        n = sum(1 for r in rows if r.get(f) not in (None, ""))
        print(f"{f:15s} {n}/{len(rows)}")
    ok = sum(1 for r in rows if r.get("required_ok"))
    print(f"{'required_ok':15s} {ok}/{len(rows)}")


# --------------------------------------------------------------------------
# CHẠY MỘT NGUỒN
# --------------------------------------------------------------------------
def crawl_source(source, test, max_per_cat, links_only=False):
    cfg = CONFIG[source]
    out_file = DATA / (f"test_{source}.jsonl" if test else f"raw_{source}.jsonl")
    seen = load_seen(out_file)

    mongo_col = None
    if os.getenv("MONGO_URI"):
        try:
            from pymongo import MongoClient
            mongo_col = MongoClient(os.environ["MONGO_URI"])["abda_cosmetics"][
                ("test_" if test else "raw_") + source]
        except Exception as e:
            print(f"[{source}] Không kết nối được MongoDB: {e}")

    cats = [c for c in cfg["categories"] if not c[2].startswith("DÁN")]
    if test:
        cats = cats[:3]
    if not cats:
        print(f"[{source}] Chưa có danh mục nào. Hãy điền URL trong file.")
        return

    count = 0
    all_links = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_context(locale="vi-VN").new_page()
        try:
            for group, cat, path in cats:
                url = path if path.startswith("http") else cfg["base"] + path
                links = collect_links(page, url, cfg["product_re"], max_per_cat)
                odd = LAST_INFO.get("odd", [])
                print(f"[{source}] {cat}: web ghi {LAST_INFO.get('web_total')} | "
                      f"lấy được {len(links)} link | link lạ chưa lấy: {len(odd)}")
                safe = re.sub(r"\W+", "_", cat)
                if odd:
                    with open(DATA / f"odd_{source}_{safe}.txt", "w", encoding="utf-8") as f:
                        f.write("\n".join(odd))
                try:
                    with open(DATA / f"links_{source}_{safe}.json", "w", encoding="utf-8") as f:
                        json.dump(sorted(links), f, ensure_ascii=False, indent=0)
                except Exception:
                    pass
                if links_only:
                    all_links[cat] = len(links)
                    continue
                for link in links:
                    if link in seen:
                        continue
                    try:
                        rec = parse_product(page, link, source, group, cat)
                    except Blocked:
                        raise
                    except Exception as e:
                        print(f"[{source}] lỗi {link}: {e}")
                        continue
                    with open(out_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    if mongo_col is not None:
                        try:
                            mongo_col.update_one({"url": link}, {"$set": rec}, upsert=True)
                        except Exception as e:
                            print(f"[{source}] lỗi Mongo: {e}")
                    seen.add(link)
                    count += 1
                    if count % 25 == 0:
                        print(f"[{source}] đã cào {count} sản phẩm (tổng trong file: {len(seen)})")
                    time.sleep(random.uniform(2, 4))
                time.sleep(5)
        except Blocked:
            print(f"[{source}] Bị chặn/xác thực. Đã lưu tiến độ, chạy lại sau để cào tiếp.")
        finally:
            browser.close()
    if links_only:
        print(f"\n[{source}] SỐ SẢN PHẨM THEO DANH MỤC: {all_links} -> TỔNG {sum(all_links.values())}")
        return
    print(f"[{source}] Xong. Tổng trong file: {len(seen)}")
    coverage(out_file)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="chạy thử nhỏ")
    ap.add_argument("--source", choices=["cocolux", "hasaki", "all"], default="all")
    ap.add_argument("--links-only", action="store_true",
                    help="chỉ đếm số sản phẩm của từng danh mục, không cào chi tiết")
    ap.add_argument("--max-per-category", type=int, default=0,
                    help="giới hạn số sản phẩm mỗi danh mục (0 = không giới hạn)")
    a = ap.parse_args()
    max_n = 3 if a.test else a.max_per_category
    sources = ["cocolux", "hasaki"] if a.source == "all" else [a.source]
    procs = [Process(target=crawl_source, args=(s, a.test, max_n, a.links_only)) for s in sources]
    for pr in procs:
        pr.start()
    for pr in procs:
        pr.join()


if __name__ == "__main__":
    main()