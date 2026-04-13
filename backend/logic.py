import asyncio
import re
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from transformers import pipeline
import torch

# Use Zero-Shot for actual intelligence (Deals/Scams)
try:
    ai_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
except Exception as e:
    print(f"AI Loading Error: {e}")
    ai_classifier = None

def get_average_price(products):
    """Calculates the baseline price for the current search"""
    prices = []
    for p in products:
        try:
            # Remove '$' and convert to float
            val = float(str(p['price']).replace("$", "").replace(",", ""))
            prices.append(val)
        except:
            continue
    return sum(prices) / len(prices) if prices else 0

def analyze_listing_quality(title: str, price_usd: str, avg_price: float):
    """Idea 2 & 4: Flag scams and calculate deal value"""
    if not ai_classifier or price_usd == "N/A" or not title:
        return "Unknown", "Neutral"

    try:
        current_price = float(str(price_usd).replace("$", "").replace(",", ""))
    except:
        return "Unknown", "Neutral"

    # Define our 'Intelligence' categories
    labels = ["legitimate product", "scam or suspicious", "accessory only"]
    
    # 1. Run AI Inference
    res = ai_classifier(title[:200], labels)
    top_label = res['labels'][0]
    
    # 2. Logic-Based Quality Assessment
    status = "Legit"
    if top_label in ["scam or suspicious", "accessory only"]:
        status = "🚩 Flagged"
    
    # 3. Deal Analysis (Idea 2)
    deal_label = "Fair Price"
    if avg_price > 0:
        if current_price < (avg_price * 0.75):
            # If it's cheap AND the AI thinks it's legit, it's a steal.
            # Otherwise, it's suspiciously cheap.
            deal_label = "🔥 Potential Steal" if status == "Legit" else "⚠️ Suspiciously Cheap"
        elif current_price > (avg_price * 1.5):
            deal_label = "💎 Premium/Overpriced"

    return status, deal_label

# Currency rates
CURRENCY_CACHE = {"EGP_TO_USD": 0.018, "CNY_TO_USD": 0.15}

async def update_exchange_rates():
    """Update currency exchange rates"""
    global CURRENCY_CACHE
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://open.er-api.com/v6/latest/USD", timeout=10)
            rates = r.json().get("rates", {})
            if "EGP" in rates:
                CURRENCY_CACHE["EGP_TO_USD"] = 1 / rates.get("EGP", 48)
            if "CNY" in rates:
                CURRENCY_CACHE["CNY_TO_USD"] = 1 / rates.get("CNY", 7.2)
            print("✅ Currency rates synced")
    except Exception as e:
        print(f"⚠️ Using fallback rates: {e}")

def apply_ai_analysis(text: str):
    """Analyze product title sentiment"""
    # Change 'analyzer' to 'ai_classifier'
    if not ai_classifier:
        return "neutral", 0.0
    try:
        # Zero-shot requires labels, so we'll use a simple fallback for this specific function
        res = ai_classifier(text[:512], candidate_labels=["positive", "negative", "neutral"])
        return res['labels'][0], round(res['scores'][0], 4)
    except:
        pass
    return "neutral", 0.0

def convert_to_usd(price_text, source):
    """Convert price to USD"""
    if not price_text:
        return "N/A"
    clean_text = price_text.replace(",", "").replace("\xa0", " ").strip()
    match = re.search(r"(\d+\.?\d*)", clean_text)
    if not match:
        return price_text
    amount = float(match.group(1))
    
    # Always try to detect currency from text first
    if "EGP" in clean_text or "ج.م" in clean_text:
        return f"${(amount * CURRENCY_CACHE['EGP_TO_USD']):.2f}"
    if "¥" in clean_text or "CNY" in clean_text or "yuan" in clean_text.lower():
        return f"${(amount * CURRENCY_CACHE['CNY_TO_USD']):.2f}"
    
    # Source-based defaults
    if source == "noon":
        return f"${(amount * CURRENCY_CACHE['EGP_TO_USD']):.2f}"
    if source == "alibaba":
        return f"${(amount * CURRENCY_CACHE['CNY_TO_USD']):.2f}"
    
    # Default to USD for Amazon, eBay, etc.
    return f"${amount:.2f}"

# ============ PLAYWRIGHT SCRAPER ============

async def scrape_with_playwright(url, source):
    """Scrape using Playwright with Stealth - optimized for better page loading"""
    try:
        print(f"🌐 Scraping {source} with Playwright...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={"longitude": -74.0060, "latitude": 40.7128},
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )            
            page = await context.new_page()

            # --- ADD THIS TURBO BLOCK HERE ---
            await page.route("**/*.{png,jpg,jpeg,svg,css,woff2,gif}", lambda route: route.abort())
            # ---------------------------------

            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            
            # Reduce sleep time since we aren't loading images
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # استنى السعر يظهر فعلاً
            try:
                await page.wait_for_selector(".a-price .a-offscreen", timeout=5000)
            except:
                pass      

            html = await page.content()
            await browser.close()
            return BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"❌ {source} Playwright error: {str(e)[:100]}")
        try:
            await browser.close()
        except:
            pass
        return None


async def get_exact_price(context, link):
    try:
        page = await context.new_page()
        await page.goto(link, wait_until="networkidle", timeout=30000)

        selectors = [
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#priceblock_saleprice",
            ".a-price .a-offscreen"
        ]

        for sel in selectors:
            try:
                elem = await page.query_selector(sel)
                if elem:
                    text = (await elem.inner_text()).strip()
                    if "$" in text:
                        await page.close()
                        return text
            except:
                continue

        await page.close()
        return None

    except:
        return None

# ============ AMAZON SCRAPER ============
async def get_amazon_products(keyword: str):
    url = f"https://www.amazon.com/s?k={keyword}"
    soup = await scrape_with_playwright(url, "amazon")
    
    if not soup:
        print("❌ Amazon: Soup is empty")
        return []
    
    products = []
    items = soup.select("div[data-component-type='s-search-result']")
    
    print(f"📦 Amazon: Processing {len(items)} items")

    for item in items:
        try:
            if "Sponsored" in item.get_text():
                continue

            prices = item.select(".a-price .a-offscreen")
            
            price_usd = None
            for p in prices:
                text = p.get_text(strip=True)
            
                if "$" in text:
                    match = re.search(r"\$(\d{1,6}(?:\.\d{2})?)", text)
                    if match:
                        price_usd = f"${match.group(1)}"
                        break
                    
                elif "EGP" in text or "ج.م" in text:
                    price_usd = convert_to_usd(text, "amazon")
                    break
            # =========================
            # ❌ Skip if still no price
            # =========================
            if not price_usd:
                continue

            # =========================
            # ✅ TITLE
            # =========================
            title_elem = item.select_one("h2 span")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # =========================
            # ✅ LINK
            # =========================
            link_elem = item.select_one("a.a-link-normal")
            link = ""
            if link_elem:
                href = link_elem.get("href", "")
                if href.startswith("/"):
                    link = "https://www.amazon.com" + href
                else:
                    link = href

            # =========================
            # ✅ IMAGE
            # =========================
            img_elem = item.select_one("img.s-image")
            image = img_elem.get("src", "") if img_elem else ""

            # =========================
            # ✅ AI ANALYSIS
            # =========================
            label, score = "neutral", 0.0
            if ai_classifier:
                try:
                    res = ai_classifier(title[:200], ["positive", "negative", "neutral"])
                    label = res["labels"][0]
                    score = round(res["scores"][0], 4)
                except:
                    pass

            products.append({
                "title": title,
                "price": price_usd,
                "link": link,
                "image": image,
                "source": "amazon",
                "ai_label": label,
                "ai_score": score
            })

        except Exception:
            continue

    print(f"✅ Amazon: Extracted {len(products)} products")
    return products
# ============ EBAY SCRAPER ============

# Replace with your actual WebScraping.ai API Key

WEBSCRAPING_AI_KEY = "afc800d7-2cd7-4df1-9e5e-452432dba589"

# ============ EBAY SCRAPER (WebScraping.ai) ============

async def get_ebay_products(keyword: str):
    """Scrape eBay using WebScraping.ai with JS rendering for reliability"""
    print(f"📡 Requesting eBay via WebScraping.ai (JS Rendered)...")
    
    target_url = f"https://www.ebay.com/sch/i.html?_nkw={keyword}&LH_BIN=1&_ipg=60"
    api_url = "https://api.webscraping.ai/html"
    
    # Switch to JS rendering and residential proxies to bypass "empty page" blocks
    params = {
        "api_key": WEBSCRAPING_AI_KEY,
        "url": target_url,
        "render": "js",         # Added JS rendering
        "proxy": "residential"  # Switched to residential for higher success
    }

    products = []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(api_url, params=params)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 1. FIND THE CONTAINERS (Check all 2026 variations)
            items = soup.select("li.s-item") or \
                    soup.select(".s-item__wrapper") or \
                    soup.select(".s-card") or \
                    soup.select(".srp-results li")

            for item in items:
                # 2. EXTRACT TITLE (Check for span or direct text)
                title_elem = item.select_one(".s-item__title") or \
                             item.select_one(".s-card__title")
                
                # eBay 2026 often wraps titles in an extra <span> for SEO
                if title_elem and title_elem.find("span"):
                    title_text = title_elem.find("span").get_text(strip=True)
                elif title_elem:
                    title_text = title_elem.get_text(strip=True)
                else:
                    continue

                # Filter out junk
                if not title_text or "shop on ebay" in title_text.lower():
                    continue

                # 3. EXTRACT PRICE & IMAGE
                price = item.select_one(".s-item__price") or item.select_one(".s-card__price")
                img_elem = item.select_one(".s-item__image-img img") or \
                           item.select_one("img[src*='ebayimg']")

                if price:
                    products.append({
                        "title": title_text.replace("New Listing", ""),
                        "price": convert_to_usd(price.text.strip(), "ebay"),
                        "link": item.find("a", href=True)['href'].split('?')[0] if item.find("a", href=True) else "",
                        "image": img_elem.get('src', img_elem.get('data-src', '')) if img_elem else "",
                        "source": "ebay"
                    })
    except Exception as e:
        print(f"🧨 eBay Source Error: {e}")
    
    return products

# ============ ALIBABA SCRAPER (WebScraping.ai) ============

async def get_alibaba_products(keyword: str):
    """Scrape Alibaba using WebScraping.ai's JS Rendering"""
    print(f"📡 Requesting Alibaba via WebScraping.ai (JS Rendered)...")
    
    target_url = f"https://www.alibaba.com/trade/search?SearchText={keyword}"
    api_url = "https://api.webscraping.ai/html"
    
    # Alibaba is JS-heavy and has tougher bot detection
    params = {
        "api_key": WEBSCRAPING_AI_KEY,
        "url": target_url,
        "render": "js",         # Required to see search results
        "proxy": "residential"  # Required to avoid being blocked by Alibaba
    }

    products = []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(api_url, params=params)
            if response.status_code != 200:
                print(f"❌ Alibaba Error: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            # Using specific selectors found in your previous version
            items = soup.select(".organic-list-offer") or soup.select("[class*='offer']")
            
            for item in items[:20]: # Limit for performance
                title = item.select_one(".organic-list-offer-outter-title-text") or item.select_one("h2")
                price = item.select_one(".search-card-e-price-main-price") or item.select_one("[class*='price']")
                link = item.find("a", href=True)
                img = item.select_one("img")

                if title and price:
                    title_text = title.text.strip()
                    label, score = apply_ai_analysis(title_text)
                    
                    href = link.get('href', '')
                    full_link = "https:" + href if href.startswith("//") else href
                    
                    products.append({
                        "title": title_text,
                        "price": convert_to_usd(price.text.strip(), "alibaba"),
                        "link": full_link,
                        "image": img.get('src', img.get('data-src', '')) if img else "",
                        "source": "alibaba",
                        "ai_label": label,
                        "ai_score": score
                    })
    except Exception as e:
        print(f"🧨 Alibaba Critical Error: {e}")
        
    print(f"✅ Alibaba: Found {len(products)} products")
    return products