import sys
import asyncio
import os

# Force Proactor Event Loop on Windows BEFORE importing anything async
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    import os
    os.environ['PYTHONPATH'] = os.getcwd()

# Disable tokenizers parallelism to prevent warnings
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# to start the server with hot-reload:
# python run.py --no-reload

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logic import (
    update_exchange_rates,
    get_amazon_products,
    get_ebay_products,
    get_walmart_products,
    get_bestbuy_products,
    analyze_listing_quality,
    get_average_price
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 AI Market Intelligence: ONLINE")
    try:
        await update_exchange_rates()
        print("✅ Exchange rates updated.")
    except Exception as e:
        print(f"⚠️ Exchange rate sync failed: {e}")
    yield
    print("🛑 Server shutting down...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI Scraper is Active"}

@app.get("/api/search")
async def search(keyword: str):
    print(f"🔍 Deep Analyzing: {keyword}")
    
    # 1. Scrape all platforms
    results = await asyncio.gather(
        #get_amazon_products(keyword),
        #get_ebay_products(keyword),
        get_walmart_products(keyword),
        get_bestbuy_products(keyword),
        return_exceptions=True
    )
    
    all_products = []
    for result in results:
        if isinstance(result, list):
            all_products.extend(result)

    # --- Pass 1: Initial AI Filtering (Identify Accessories/Scams) ---
    # We pass 0 for avg_price because we don't know it yet
    legit_products_for_avg = []
    
    for product in all_products:
        status, _ = analyze_listing_quality(product['title'], product['price'], 0)
        product['ai_status'] = status
        
        # Only use this product for the average if AI says it's the actual item
        if status == "Legit":
            legit_products_for_avg.append(product)

    # --- Pass 2: Calculate CLEAN Market Average ---
    # This prevents a $5 PS5 sticker from lowering the average of a $500 console
    avg_market_price = get_average_price(legit_products_for_avg)
    print(f"📊 Clean Market Average (No Accessories): ${avg_market_price:.2f}")

    # --- Pass 3: Final Deal Analysis ---
    # Now we know the REAL average, we can see who has a good deal
    for product in all_products:
        _, deal = analyze_listing_quality(
            product['title'], 
            product['price'], 
            avg_market_price
        )
        product['ai_deal'] = deal

    return {
        "keyword": keyword,
        "market_average": f"${avg_market_price:.2f}",
        "total_found": len(all_products),
        "legit_count": len(legit_products_for_avg),
        "results": all_products
    }