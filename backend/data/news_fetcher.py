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

def fetch_newsapi_headlines(query: str, max_results: int = 5) -> list:
    if not settings.NEWS_API_KEY or settings.NEWS_API_KEY == "placeholder":
        return []
        
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"{query} India stock",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max_results,
            "apiKey": settings.NEWS_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        
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
            logger.warning(f"NewsAPI error: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching NewsAPI for {query}: {e}")
        return []

def fetch_market_news() -> list:
    # Combine macro news
    macro_queries = ["Indian stock market", "RBI policy", "Nifty 50"]
    all_news = []
    
    for q in macro_queries:
        all_news.extend(fetch_google_news(q, max_results=2))
        
    return all_news

def fetch_all_news_for_stock(symbol: str) -> list:
    company_name = symbol.replace(".NS", "").replace(".BO", "")
    
    news = []
    news.extend(fetch_google_news(company_name, 3))
    news.extend(fetch_newsapi_headlines(company_name, 2))
    
    return news
