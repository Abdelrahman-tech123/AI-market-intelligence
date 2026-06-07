import re
import asyncio
import httpx
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
from transformers import pipeline

CURRENT_RATE = 48.50

# Enhanced AI Suite
try:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")  # type: ignore
    sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")  # type: ignore
except Exception as e:
    print(f"AI Loading Error: {e}")
    classifier = None
    sentiment_analyzer = None
    
def extract_specs(title):
    """Automatically pulls technical specs from the title for web UI chips."""
    specs = {
        "ram": re.search(r'(\d+GB|\d+gb)\s*RAM', title, re.I),
        "storage": re.search(r'(\d+TB|\d+GB)\s*(SSD|HDD|NVMe|Storage)', title, re.I),
        "cpu": re.search(r'(i3|i5|i7|i9|Ryzen \d|M1|M2|M3)', title, re.I)
    }
    return {k: v.group(0) if v else None for k, v in specs.items()}

def analyze_listing_quality(title, price_usd, avg_price):
    """
    The 'Brain' of the operation. Returns a structured dictionary of 
    expert opinions and scores to display on your web app.
    """
    analysis = {
        "status": "Legit",
        "badge": "Standard",
        "value_score": 50,
        "opinion": "Fair market price.",
        "specs": extract_specs(title)
    }

    if not price_usd or price_usd == "N/A":
        analysis["status"] = "Unknown"
        return analysis["status"], analysis

    try:
        price = float(price_usd.replace("$", "").replace(",", ""))
    except:
        analysis["status"] = "Unknown"
        return analysis["status"], analysis

    # 1. AI Content Validation (Legit check)
    if classifier:
        labels = ["genuine electronic device", "replacement part", "accessory", "suspicious listing"]
        try:
            res = classifier(title[:256], labels)
            top_label = res['labels'][0]
            
            if top_label == "suspicious listing":
                analysis["status"] = "🚩 Flagged"
                analysis["opinion"] = "Listing looks unprofessional or suspicious."
            elif top_label in ["replacement part", "accessory"]:
                analysis["status"] = "⚠️ Component"
                analysis["opinion"] = "This appears to be an accessory or individual component part."
        except Exception as ai_err:
            print(f"Classifier error: {ai_err}")

    # 2. Advanced Pricing Logic
    if avg_price > 0:
        ratio = price / avg_price
        
        if ratio < 0.5:
            analysis["value_score"] = 95
            analysis["badge"] = "🔥 Steal"
            analysis["opinion"] = "Extremely low price. Verify seller ratings before buying."
        elif ratio < 0.85:
            analysis["value_score"] = 85
            analysis["badge"] = "✅ Great Deal"
            analysis["opinion"] = "Solid savings compared to the average market price."
        elif ratio > 1.4:
            analysis["value_score"] = 20
            analysis["badge"] = "💎 Premium"
            analysis["opinion"] = "Priced significantly above market average."
        else:
            analysis["value_score"] = 60
            analysis["badge"] = "Fair Price"
            analysis["opinion"] = "Competitively priced within market range."

    # 3. Sentiment Analysis (Is this a high-confidence title format?)
    if sentiment_analyzer:
        try:
            sent = sentiment_analyzer(title[:256])[0]
            if sent['label'] == 'POSITIVE' and sent['score'] > 0.9:
                analysis["opinion"] += " High listing confidence."
        except Exception:
            pass

    return analysis["status"], analysis

def get_average_price(products):
    """Calculates the baseline USD price for the current search results."""
    prices = []
    for p in products:
        try:
            price_str = str(p['price']).replace(",", "")
            match = re.search(r"[-+]?\d*\.\d+|\d+", price_str)
            if not match:
                continue
            
            val = float(match.group())
            if "EGP" in price_str or "ج.م" in price_str:
                val = val / CURRENT_RATE
                
            prices.append(val)
        except Exception:
            continue
    return sum(prices) / len(prices) if prices else 0.0

async def update_exchange_rates():
    """Fetches real-time EGP exchange rate from API."""
    global CURRENT_RATE
    url = "https://open.er-api.com/v6/latest/USD"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            if data.get("result") == "success":
                CURRENT_RATE = data["rates"]["EGP"]
                print(f"🚀 Real-time Currency Sync: 1 USD = {CURRENT_RATE:.2f} EGP")
            else:
                print("⚠️ API returned an error, using fallback.")
    except Exception as e:
        print(f"❌ Currency API unreachable: {e}. Using fallback {CURRENT_RATE}")

def exchange_usd_egp(price_str):
    """Convert price string from EGP to USD if necessary."""
    try:
        raw_numeric = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        if not raw_numeric:
            return 0.0
        numeric_value = float(raw_numeric)
        
        if "EGP" in price_str or "ج.m" in price_str or "ج.م" in price_str:
            return numeric_value / CURRENT_RATE
        return numeric_value
    except Exception:
        return 0.0

def convert_to_usd(price_str):
    """Formats raw price strings cleanly into a USD string."""
    price_value = exchange_usd_egp(price_str)
    return f"${price_value:.2f}" if price_value > 0 else None

# ============ PLAYWRIGHT CONFIGURATION ============
SOURCE_READY_SELECTORS = {
    "amazon": ["div[data-component-type='s-search-result']", "[data-cel-widget='search_result_0']", ".s-main-slot"],
}

async def _wait_for_any_selector(page, selectors, timeout=12000):
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return selector
        except (PlaywrightTimeoutError, Exception):
            continue
    return None

async def _navigate_and_capture(page, url, source):
    """Navigates to URL using tiered wait states to balance speed and reliability."""
    selectors = SOURCE_READY_SELECTORS.get(source, [])
    attempts = [
        ("domcontentloaded", 45000),
        ("load", 45000),
    ]

    for wait_until, timeout in attempts:
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            if selectors:
                matched = await _wait_for_any_selector(page, selectors, timeout=12000)
                if matched:
                    print(f"✅ {source}: ready selector matched: {matched}")
            await page.wait_for_timeout(2000)
            return await page.content()
        except PlaywrightTimeoutError:
            try:
                html = await page.content()
                if html and len(html) > 2000:
                    return html
            except Exception:
                pass
        except Exception:
            continue
    return None

async def _block_nonessential_assets(route):
    """Aborts visual asset payloads to save massive structural bandwidth."""
    if route.request.resource_type in ["image", "font", "media"]:
        await route.abort()
    else:
        await route.continue_()

# ============ AMAZON SCRAPER ============
async def get_amazon_products(keyword: str, max_results: int = 25):
    """
    Fetches up to `max_results` products across multiple pages.
    Intelligently bypasses accessory filters if the user is explicitly searching for one.
    """
    unwanted_keywords = [
        "case", "cover", "sleeve", "charger", "adapter", "cable", "cord", 
        "bag", "backpack", "stand", "hub", "dock", "screen protector", "sticker"
    ]
    
    keyword_lower = keyword.lower()
    searching_for_accessory = any(unwanted in keyword_lower for unwanted in unwanted_keywords)
    
    if searching_for_accessory:
        print("💡 User is searching for an accessory. Disabling strict accessory block.")
    else:
        print("🔒 User is searching for a main device. Strict accessory block is ACTIVE.")

    products = []
    current_page = 1
    max_pages = 4  
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-http2',
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--window-size=1920,1080'
        ])

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="en-US"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        while len(products) < max_results and current_page <= max_pages:
            print(f"🔍 Crawling Amazon page {current_page}... (Collected: {len(products)}/{max_results})")
            
            url = f"https://www.amazon.com/s?k={quote_plus(keyword)}&page={current_page}"
            page = await context.new_page()
            await page.route("**/*", _block_nonessential_assets)
            
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            html = await _navigate_and_capture(page, url, "amazon")
            if not html:
                print(f"⚠️ Failed to get HTML for page {current_page}")
                await page.close()
                break

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            final_html = await page.content()
            await page.close()

            soup = BeautifulSoup(final_html, "html.parser")
            items = soup.select("div[data-component-type='s-search-result']")
            if not items:
                items = soup.select("[data-cel-widget^='search_result_']")

            if not items:
                print("🛑 No more raw item boxes found on this page. Stopping.")
                break

            for item in items:
                try:
                    if "Sponsored" in item.get_text():
                        continue

                    # 1. Extract Title
                    title_elem = item.select_one("h2 span")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # 2. Conditional Accessory Filter Check
                    if not searching_for_accessory:
                        title_lower = title.lower()
                        if any(unwanted in title_lower for unwanted in unwanted_keywords):
                            continue 

                    # 3. Extract Price
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
                            converted = convert_to_usd(text)
                            if converted:
                                price_usd = converted
                                break
                    
                    if not price_usd:
                        continue

                    # 4. Extract product link
                    link_elem = item.select_one("a.a-link-normal")
                    link = ""
                    if link_elem:
                        href = str(link_elem.get("href", "") or "")
                        link = "https://www.amazon.com" + href if href.startswith("/") else href

                    # 5. Extract image URL
                    img_elem = item.select_one("img.s-image")
                    image = img_elem.get("src", "") if img_elem else ""

                    if not any(prod["link"] == link for prod in products):
                        products.append({
                            "title": title,
                            "price": price_usd,
                            "link": link,
                            "image": image,
                            "source": "amazon",
                        })

                    if len(products) >= max_results:
                        break

                except Exception:
                    continue
            
            current_page += 1

        await browser.close()

    print(f"✅ Amazon: Extracted {len(products)} products total.")
    return products