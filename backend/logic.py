import re
import asyncio
import httpx
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
from transformers import pipeline
from config import settings

CURRENT_RATE = 48.50
ebay_api_key = settings.ebay_app_id
ebay_cert_key = settings.ebay_cert_id

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
            if val:
                prices.append(val)
            else:
                val = float(str(p['price']).replace("EGP", "").replace(",", ""))
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
async def update_exchange_rates():
    global CURRENT_RATE
    url = "https://open.er-api.com/v6/latest/USD"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            if data["result"] == "success":
                # Extract EGP from the rates dictionary
                CURRENT_RATE = data["rates"]["EGP"]
                print(f"🚀 Real-time Currency Sync: 1 USD = {CURRENT_RATE:.2f} EGP")
            else:
                print("⚠️ API returned an error, using fallback.")
                
    except Exception as e:
        print(f"❌ Currency API unreachable: {e}. Using fallback {CURRENT_RATE}")


def exchange_usd_egp(price_str, source):
    """Convert between USD and EGP currencies"""
    try:
        raw_numeric = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        if not raw_numeric:
            return 0.0
        numeric_value = float(raw_numeric)
        
        if "EGP" in price_str or "ج.م" in price_str:
            return numeric_value / CURRENT_RATE
        elif "$" in price_str:
            return numeric_value
        return numeric_value
    except:
        return 0.0

def convert_to_usd(price_str, source):
    """Convert any price string to USD format"""
    try:
        price_value = exchange_usd_egp(price_str, source)
        if price_value > 0:
            return f"${price_value:.2f}"
        return None
    except:
        return None

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

# ============ PLAYWRIGHT SCRAPER ============

SOURCE_READY_SELECTORS = {
    "amazon": [
        "div[data-component-type='s-search-result']",
        "[data-cel-widget='search_result_0']",
        ".s-main-slot",
    ],
    "ebay": [
        ".srp-river-results",
        "ul.srp-results",
        ".s-item__title",
        "#srp-river-results",
    ],
    "bestbuy": [
        ".sku-item",                        
        ".list-items",
        "ol.sku-list",
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
            await page.wait_for_timeout(3000)
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
                '--disable-http2',
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
            # Inside scrape_with_playwright, before grabbing html:
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()

            # Apply the optimized turbo block
            await page.route("**/*", _block_nonessential_assets)

            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            
            # Go to page
            html = await _navigate_and_capture(page, url, source)
            if source == "ebay":
                try:
                    # Wait specifically for the results container to exist
                    await page.wait_for_selector(".srp-results, .s-item", timeout=10000)
                except:
                    print("⚠️ eBay: Search results didn't load in time.")
            
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
        print("❌ Amazon: Failed to load page")
        return []
    
    products = []
    items = soup.select("div[data-component-type='s-search-result']")
    
    if not items:
        items = soup.select("[data-cel-widget^='search_result_']")
    
    print(f"📦 Amazon: Found {len(items)} items")

    for item in items:
        try:
            # Skip sponsored results
            if "Sponsored" in item.get_text():
                continue

            # Extract price
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
                    converted = convert_to_usd(text, "amazon")
                    if converted:
                        price_usd = converted
                        break
            
            # Skip if no valid price found
            if not price_usd:
                continue

            # Extract title
            title_elem = item.select_one("h2 span")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            
            # Extract link
            link_elem = item.select_one("a.a-link-normal")
            link = ""
            if link_elem:
                href = str(link_elem.get("href", "") or "")
                if href.startswith("/"):
                    link = "https://www.amazon.com" + href
                else:
                    link = href

            # Extract image
            img_elem = item.select_one("img.s-image")
            image = img_elem.get("src", "") if img_elem else ""

            products.append({
                "title": title,
                "price": price_usd,
                "link": link,
                "image": image,
                "source": "amazon",
            })

            if len(products) >= 10:
                break
                
        except Exception as e:
            continue

    print(f"✅ Amazon: Extracted {len(products)} products")
    return products

# ============ EBAY API SCRAPER ============
async def get_ebay_products(keyword: str):
    print(f"📡 Scraping eBay for: '{keyword}'...")

    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(keyword)}&LH_BIN=1&_ipg=10"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
    }

    products = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, http2=False) as client:
            response = await client.get(url, headers=headers, timeout=15.0)

            if response.status_code != 200:
                print(f"❌ eBay scrape failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("li.s-item")

            if not items:
                items = soup.select("[class*='s-item']")

            print(f"📦 eBay: Found {len(items)} items")

            for item in items:
                try:
                    title_el = item.select_one(".s-item__title")
                    price_el = item.select_one(".s-item__price")
                    link_el = item.select_one("a.s-item__link")
                    image_el = item.select_one("img.s-item__image-img")

                    title = title_el.get_text(strip=True) if title_el else ""
                    price = price_el.get_text(strip=True) if price_el else ""
                    href = link_el["href"] if link_el else ""
                    image = image_el.get("src") or image_el.get("data-src", "") if image_el else ""

                    if not title or "shop on ebay" in title.lower():
                        continue

                    products.append({
                        "title": title,
                        "price": convert_to_usd(price, "ebay"),
                        "link": href,
                        "image": image,
                        "source": "ebay",
                    })

                    if len(products) >= 10:
                        break

                except Exception:
                    continue

    except httpx.RequestError as e:
        print(f"❌ eBay connection error: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected eBay error: {e}")
        return []

    print(f"✅ eBay: Extracted {len(products)} products")
    return products


# ============ BTECH SCRAPER============

async def get_btech_products(keyword: str):
    # Construct your search URL
    url = f"https://btech.com/en/s?q={quote_plus(keyword)}"
    
    # Use your Playwright helper
    soup = await scrape_with_playwright(url, "btech")
    if not soup:
        return []

    products = []
    
    # 1. Target the 'article' tag which holds the entire product card
    items = soup.find_all("article")
    
    print(f"📦 B.TECH: Processing {len(items)} items")

    for item in items:
        try:
            # 2. TITLE: Find an <a> with a title attribute, without using lambda/class_ to satisfy type-checkers
            from typing import Any
            tag: Any = item

            link_elem = None
            for a in tag.find_all("a"):
                title_attr = a.get("title")
                if title_attr and isinstance(title_attr, str) and title_attr.strip():
                    link_elem = a
                    break

            if not link_elem:
                # fallback: first anchor with href
                for a in tag.find_all("a", href=True):
                    link_elem = a
                    break

            if not link_elem:
                continue

            title = str(link_elem.get("title") or "").strip()

            # --- FREELANCER FILTER ---
            if any(x in title.lower() for x in ['cover', 'case', 'glass', 'adapter']):
                continue

            # 3. PRICE: Found in the footer -> div -> spans
            # We look for the span with 'text-medium' which holds the actual number
            price_val = tag.select_one("span.text-medium")
            if not price_val:
                continue
            
            # Clean the price string (remove commas)
            price_text = price_val.get_text(strip=True).replace(',', '')
            price_egp = f"EGP {price_text}"

            # 4. IMAGE: Found in the <header> img tag
            img_elem = tag.find("img")
            image = ""
            if img_elem:
                image = str(img_elem.get("src") or img_elem.get("data-src") or "")

            # 5. LINK: From the link element we found earlier
            link = "https://btech.com" + str(link_elem.get("href") or "")

            products.append({
                "title": title,
                "price": price_egp,
                "link": link,
                "image": image,
                "source": "btech",
                "ai_label": "neutral",
                "ai_score": 0.0
            })

            if len(products) >= 5: break
            
        except Exception as e:
            print(f"⚠️ B.TECH parse error: {e}")
            continue

    print(f"✅ B.TECH: Extracted {len(products)} products")
    return products