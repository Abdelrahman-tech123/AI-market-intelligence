import json
import re
import asyncio
import re
import httpx
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
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

SOURCE_READY_SELECTORS = {
    "amazon": [
        "div[data-component-type='s-search-result']",
        "[data-cel-widget='search_result_0']",
        ".s-main-slot",
    ],
    "alibaba": [
        ".search-card-wrapper",
        ".list-no-v2-main",
        "[class*='gallery-card']",
        "[class*='offer-card']",
        "a[href*='/product-detail/']",
        "a[href*='product-detail']",
        '[data-testid="search-result"]',
    ],
}

async def _wait_for_any_selector(page, selectors, timeout=12000):
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return selector
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return None


async def _navigate_and_capture(page, url, source):
    """Use looser readiness checks than networkidle and keep partial HTML on timeout."""
    selectors = SOURCE_READY_SELECTORS.get(source, [])
    attempts = [
        ("domcontentloaded", 45000),
        ("load", 45000),
        ("commit", 30000),
    ]

    for wait_until, timeout in attempts:
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            if selectors:
                matched = await _wait_for_any_selector(page, selectors, timeout=12000)
                if matched:
                    print(f"✅ {source}: ready selector matched after {wait_until}: {matched}")
                else:
                    print(f"⚠️ {source}: navigation succeeded but no ready selector matched after {wait_until}")
            await page.wait_for_timeout(1500)
            return await page.content()
        except PlaywrightTimeoutError:
            print(f"⚠️ {source}: goto timed out with wait_until={wait_until}, checking partial content")
            try:
                if selectors:
                    matched = await _wait_for_any_selector(page, selectors, timeout=6000)
                    if matched:
                        print(f"✅ {source}: recovered from timeout using partial DOM: {matched}")
                        await page.wait_for_timeout(1000)
                        return await page.content()

                html = await page.content()
                if html and len(html) > 2000:
                    print(f"⚠️ {source}: using partial HTML after timeout ({len(html)} chars)")
                    return html
            except Exception:
                pass
        except Exception as nav_error:
            print(f"⚠️ {source}: navigation attempt failed with wait_until={wait_until}: {str(nav_error)[:120]}")

    return None

async def _block_nonessential_assets(route):
    """Block heavy visual assets but allow data-carrying scripts."""
    # List of types that are safe to block without breaking the data
    excluded_types = ["image", "font", "media"]
    
    if route.request.resource_type in excluded_types:
        await route.abort()
    else:
        await route.continue_()
        
async def scrape_with_playwright(url, source):
    browser = None
    try:
        print(f"🌐 Scraping {source} with Playwright...")
        async with async_playwright() as p:
            # Added more flags to look like a real browser
            browser = await p.chromium.launch(headless=True, args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080'
            ])
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="en-US", # Crucial for Walmart/Best Buy
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/" # Makes it look like you came from a search
                }
            )
            # --- THE MAGIC FIX FOR ALIEXPRESS ---
            # This hides the 'bot' flag even if the stealth plugin fails
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()

            # Apply the optimized turbo block
            await page.route("**/*", _block_nonessential_assets)

            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            
            # Go to page
            html = await _navigate_and_capture(page, url, source)
            if source in ["walmart", "bestbuy"]:
                # Scroll down to trigger lazy-loading
                await page.mouse.wheel(0, 1500) 
                await asyncio.sleep(2) # Give it a second to render
            
            if not html:
                await browser.close()
                return None

           
            # Final capture
            final_html = await page.content()
            await browser.close()
            return BeautifulSoup(final_html, "html.parser")
            
    except Exception as e:
        print(f"❌ {source} Playwright error: {str(e)[:100]}")
        return None
    

async def get_exact_price(context, link):
    try:
        page = await context.new_page()
        html = await _navigate_and_capture(page, link, "amazon")
        if not html:
            await page.close()
            return None

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
    url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
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

            products.append({
                "title": title,
                "price": price_usd,
                "link": link,
                "image": image,
                "source": "amazon",
                "ai_label": "neutral",
                "ai_score": 0.0
            })

            if len(products) >= 5: break
        except Exception:
            continue

    # 2. BATCH AI ANALYSIS (Outside the loop)
    if ai_classifier and products:
        titles = [p["title"][:200] for p in products]
        try:
            # Most modern classifiers can handle a list of strings for speed
            results = ai_classifier(titles, ["positive", "negative", "neutral"])
            for i, res in enumerate(results):
                products[i]["ai_label"] = res["labels"][0]
                products[i]["ai_score"] = round(res["scores"][0], 4)
        except:
            pass # Fallback to neutral if batch fails

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

            for item in items[:15]:
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
                if len(products) >= 7:
                    break
    except Exception as e:
        print(f"🧨 eBay Source Error: {e}")
    
    return products

# ============ Walmart SCRAPER (WebScraping.ai) ============

def _normalize_external_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    return url

async def get_walmart_products(keyword: str):
    url = f"https://www.walmart.com/search?q={keyword}"
    soup = await scrape_with_playwright(url, "walmart")
    
    if not soup: return []

    products = []
    # 2026 Updated Selectors: Walmart often uses data-testid or generic grid classes
    items = soup.select("div[data-testid='item-stack'] > div") or \
            soup.select("[data-item-id]") or \
            soup.select(".mb0.ph0-xl")

    for item in items:
        try:
            # Title extraction
            title_elem = item.select_one("span[itemprop='name']") or \
                         item.select_one(".normal") or \
                         item.select_one("a.ld")
            if not title_elem: continue
            title = title_elem.get_text(strip=True)

            # Price extraction (Walmart prices are often in a 'current-price' container)
            price_elem = item.select_one("[data-automation-id='current-price']") or \
                         item.select_one(".w_iUH7") or \
                         item.select_one("div.mr1.mr2-sm")
            
            raw_price = price_elem.get_text(strip=True) if price_elem else ""
            # Regex to clean up price (extracts $XXX.XX)
            match = re.search(r"(\$\d+\.\d{2})", raw_price.replace("current price", ""))
            price_text = match.group(1) if match else raw_price

            # Link & Image
            link_elem = item.select_one("a[href*='/ip/']")
            href = link_elem.get("href", "") if link_elem else ""
            if href.startswith("/"): href = "https://www.walmart.com" + href
            
            img_elem = item.select_one("img")
            image = img_elem.get("src") if img_elem else ""

            if title and price_text:
                products.append({
                    "title": title, 
                    "price": price_text, 
                    "link": href.split('?')[0],
                    "image": image, 
                    "source": "walmart", 
                    "ai_label": "neutral", 
                    "ai_score": 0.0
                })
        except: continue
        
    return products

# ============ BestBuy SCRAPER (WebScraping.ai) ============

async def get_bestbuy_products(keyword: str):
    url = f"https://www.bestbuy.com/site/searchpage.jsp?st={keyword}"
    soup = await scrape_with_playwright(url, "bestbuy")
    
    if not soup: return []

    products = []
    # Best Buy uses sku-item-list or specific gallery classes
    items = soup.select(".sku-item") or \
            soup.select(".list-item") or \
            soup.select(".grid-item")

    for item in items:
        try:
            # Title
            title_elem = item.select_one(".sku-title a") or \
                         item.select_one(".sku-header a")
            if not title_elem: continue
            title = title_elem.get_text(strip=True)

            # Price
            price_elem = item.select_one(".priceView-customer-price span") or \
                         item.select_one("[class*='priceView-customer-price']")
            
            price_text = price_elem.get_text(strip=True) if price_elem else "N/A"

            # Link & Image
            href = title_elem.get("href", "")
            if href.startswith("/"): href = "https://www.bestbuy.com" + href
            
            img_elem = item.select_one("img.product-image") or item.select_one("img")
            image = img_elem.get("src") if img_elem else ""

            products.append({
                "title": title, 
                "price": price_text, 
                "link": href.split('?')[0],
                "image": image, 
                "source": "bestbuy", 
                "ai_label": "neutral", 
                "ai_score": 0.0
            })
        except: continue
        
    return products