import feedparser
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import datetime
from config import settings
from utils.logger import setup_logger
from utils.api_manager import api_key_manager
from utils.cache import ttl_cache

logger = setup_logger("news_fetcher")

def tag_sentiment(headline: str) -> str:
    headline_lower = headline.lower()
    positive_words = ["surge", "profit", "beat", "upgrade", "bullish", "record",
                      "growth", "strong", "outperform", "expansion", "rally", "jump"]
    negative_words = ["crash", "loss", "downgrade", "bearish", "selloff", "decline",
                      "weak", "miss", "fraud", "default", "slump", "fall", "drop"]

    pos_count = sum(1 for word in positive_words if word in headline_lower)
    neg_count = sum(1 for word in negative_words if word in headline_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"

def fetch_google_news(query: str, max_results: int = 5) -> list:
    try:
        encoded_query = quote(f"{query} stock India")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:max_results]:
            articles.append({
                "headline": entry.title,
                "source": "google_rss",
                "url": entry.link,
                "sentiment": tag_sentiment(entry.title),
                "published_at": entry.published,
                "query": query
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching Google News for {query}: {e}")
        return []

def fetch_newsapi_headlines(query: str, max_results: int = 5) -> list:
    api_key = api_key_manager.get_key("newsapi")
    if not api_key:
        logger.error("All NewsAPI keys are exhausted or not configured!")
        return []
        
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"{query} India stock",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max_results,
            "apiKey": api_key
        }
        
        # Log usage
        api_key_manager.record_usage("newsapi", api_key)
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 429:
            logger.warning("NewsAPI rate limited. Marking key exhausted.")
            api_key_manager.mark_exhausted("newsapi", api_key)
            return []
            
        if response.status_code == 200:
            data = response.json()
            articles = []
            for item in data.get("articles", [])[:max_results]:
                articles.append({
                    "headline": item.get("title", ""),
                    "source": "newsapi",
                    "url": item.get("url", ""),
                    "sentiment": tag_sentiment(item.get("title", "")),
                    "published_at": item.get("publishedAt", ""),
                    "query": query
                })
            return articles
        else:
            logger.warning(f"NewsAPI failed (status {response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"Error fetching NewsAPI: {e}")
        
    return []

COMPANY_NAME_MAP = {
    "RELIANCE.NS": "Reliance Industries",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "State Bank of India",
    "INFY.NS": "Infosys",
    "TCS.NS": "Tata Consultancy Services",
    "HCLTECH.NS": "HCL Technologies",
    "WIPRO.NS": "Wipro",
    "SUNPHARMA.NS": "Sun Pharma",
    "CIPLA.NS": "Cipla",
    "HFCL.NS": "HFCL",
    "TECHM.NS": "Tech Mahindra",
    "BSE.NS": "BSE",
    "ITC.NS": "ITC",
    "LT.NS": "Larsen & Toubro",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "AXISBANK.NS": "Axis Bank",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "MARUTI.NS": "Maruti Suzuki",
    "TATAMOTORS.NS": "Tata Motors",
    "TATASTEEL.NS": "Tata Steel",
    "ASIANPAINT.NS": "Asian Paints",
    "BAJFINANCE.NS": "Bajaj Finance",
    "M&M.NS": "Mahindra & Mahindra",
    "BHARTIARTL.NS": "Bharti Airtel",
    "ONGC.NS": "ONGC",
    "NTPC.NS": "NTPC",
    "POWERGRID.NS": "Power Grid",
    "ULTRACEMCO.NS": "UltraTech Cement",
    "TITAN.NS": "Titan",
    "BAJAJFINSV.NS": "Bajaj Finserv",
    "NESTLEIND.NS": "Nestle India",
    "JSWSTEEL.NS": "JSW Steel",
    "GRASIM.NS": "Grasim",
    "HDFCLIFE.NS": "HDFC Life",
    "SBILIFE.NS": "SBI Life",
    "DRREDDY.NS": "Dr Reddy",
    "INDUSINDBK.NS": "IndusInd Bank",
    "DIVISLAB.NS": "Divis Labs",
    "APOLLOHOSP.NS": "Apollo Hospitals",
    "ADANIENT.NS": "Adani Enterprises",
    "ADANIPORTS.NS": "Adani Ports",
    "BRITANNIA.NS": "Britannia",
    "HEROMOTOCO.NS": "Hero MotoCorp",
    "EICHERMOT.NS": "Eicher Motors",
    "COALINDIA.NS": "Coal India",
    "TATACONSUM.NS": "Tata Consumer",
    "BPCL.NS": "BPCL",
    "UPL.NS": "UPL",
    "HINDALCO.NS": "Hindalco",
}

def fetch_moneycontrol_news(company_name: str, max_results: int = 5) -> list:
    """Queries Moneycontrol articles specifically via Google RSS search to avoid fragile scraping."""
    try:
        encoded_query = quote(f"{company_name} site:moneycontrol.com")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:max_results]:
            # Remove " - Moneycontrol" suffix from title for cleaner LLM ingestion
            clean_title = entry.title
            if " - Moneycontrol" in clean_title:
                clean_title = clean_title.split(" - Moneycontrol")[0]
            elif " | Moneycontrol" in clean_title:
                clean_title = clean_title.split(" | Moneycontrol")[0]

            articles.append({
                "headline": clean_title,
                "source": "Moneycontrol",
                "url": entry.link,
                "sentiment": tag_sentiment(clean_title),
                "published_at": entry.published if hasattr(entry, "published") else str(datetime.now()),
                "query": company_name
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching Moneycontrol news for {company_name}: {e}")
        return []

@ttl_cache(seconds=1800)
def fetch_market_news() -> list:
    # Combine macro news
    macro_queries = ["Indian stock market", "RBI policy", "Nifty 50"]
    all_news = []
    
    # 1. Fetch official Moneycontrol Market Outlook Feed
    try:
        feed = feedparser.parse("https://www.moneycontrol.com/rss/marketoutlook.xml")
        for entry in feed.entries[:3]:
            all_news.append({
                "headline": entry.title,
                "source": "Moneycontrol RSS",
                "url": entry.link,
                "sentiment": tag_sentiment(entry.title),
                "published_at": entry.published if hasattr(entry, "published") else str(datetime.now()),
                "query": "Market Outlook"
            })
    except Exception as e:
        logger.error(f"Error reading Moneycontrol Market Outlook RSS: {e}")

    # 2. Supplementary Google News queries
    for q in macro_queries:
        all_news.extend(fetch_google_news(q, max_results=1))
        
    return all_news

@ttl_cache(seconds=1800)
def fetch_all_news_for_stock(symbol: str) -> list:
    company_name = COMPANY_NAME_MAP.get(symbol, symbol.replace(".NS", "").replace(".BO", ""))
    
    news = []
    # 1. Prioritize real-time Moneycontrol coverage
    news.extend(fetch_moneycontrol_news(company_name, 3))
    # 2. Fallback to Google news
    news.extend(fetch_google_news(company_name, 2))
    # 3. API headlines
    news.extend(fetch_newsapi_headlines(company_name, 1))
    
    return news
