import sys
import asyncio
import os
from dotenv import load_dotenv

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    os.environ['PYTHONPATH'] = os.getcwd()

os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logic import (
    update_exchange_rates,
    get_amazon_products,
    analyze_listing_quality,
    get_average_price
)

load_dotenv()
DEBUG_MODE = os.getenv("DEBUG_MODE", "True") == "True"

def debug_print(*args, **kwargs):
    if DEBUG_MODE:
        print(*args, **kwargs)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 AI Market Intelligence: ONLINE")
    try:
        await update_exchange_rates()
        print("✅ Exchange rates updated successfully.")
    except Exception as e:
        print(f"⚠️ Exchange rate sync failed: {e}")
    yield
    print("🛑 Server shutting down...")

app = FastAPI(lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:3000",                  
    "http://127.0.0.1:3000",                  
]

production_url = os.getenv("REACT_PUBLIC_BASE_URL")
if production_url:
    ALLOWED_ORIGINS.append(production_url.strip().rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
    allow_credentials=True,                   
    allow_methods=["*"],                      
    allow_headers=["*"],                      
)

@app.get("/")
async def root():
    return {"message": "AI Scraper is Active"}

@app.get("/api/search")
async def search(keyword: str):
    debug_print(f"🔍 Deep Analyzing: {keyword}")
    
    results = await asyncio.gather(
        get_amazon_products(keyword),
        return_exceptions=True
    )
    
    all_products = []
    for result in results:
        if isinstance(result, list):
            all_products.extend(result)

    # --- Pass 1: Baseline Context Initialization ---
    legit_products_for_avg = []
    
    for product in all_products:
        status, _ = analyze_listing_quality(product['title'], product['price'], 0)
        product['ai_status'] = status
        
        # Collect items for averaging (Accept both Legit status types or components if needed)
        if "Legit" in status or "Component" in status:
            legit_products_for_avg.append(product)

    # --- Pass 2: Clean Baseline Averaging Execution ---
    avg_market_price = get_average_price(legit_products_for_avg)
    debug_print(f"📊 Clean Market Average: ${avg_market_price:.2f}")

    # --- Pass 3: Detailed Multi-Dimensional Analysis Engine ---
    for product in all_products:
        _, detail_analysis = analyze_listing_quality(
            product['title'], 
            product['price'], 
            avg_market_price
        )
        
        product['ai_status'] = detail_analysis.get("status", "Unknown")
        product['ai_deal'] = detail_analysis.get("badge", "Standard")
        product['value_score'] = detail_analysis.get("value_score", 50)
        product['opinion'] = detail_analysis.get("opinion", "No analysis available.")
        product['ai_analysis'] = detail_analysis

    return {
        "keyword": keyword,
        "market_average": f"${avg_market_price:.2f}",
        "total_found": len(all_products),
        "legit_count": len(legit_products_for_avg),
        "results": all_products
    }