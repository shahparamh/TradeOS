import feedparser
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import datetime
from config import settings
from utils.logger import setup_logger

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

_current_key_index = 0

def fetch_newsapi_headlines(query: str, max_results: int = 5) -> list:
    global _current_key_index
    keys = [k for k in settings.NEWS_API_KEYS if k and k != "placeholder"]
    if not keys:
        return []
        
    num_keys = len(keys)
    for i in range(num_keys):
        idx = (_current_key_index + i) % num_keys
        api_key = keys[idx]
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f"{query} India stock",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_results,
                "apiKey": api_key
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                _current_key_index = idx # Save working key index
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
                logger.warning(f"NewsAPI key {api_key[:6]}... failed (status {response.status_code}). Trying next key...")
        except Exception as e:
            logger.error(f"Error fetching NewsAPI with key {api_key[:6]}...: {e}")
            
    logger.error("All NewsAPI keys are exhausted or failed!")
    return []

COMPANY_NAME_MAP = {
    "HFCL.NS": "HFCL",
    "INFY.NS": "Infosys",
    "TECHM.NS": "Tech Mahindra",
    "HCLTECH.NS": "HCL Technologies",
    "BSE.NS": "BSE",
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
