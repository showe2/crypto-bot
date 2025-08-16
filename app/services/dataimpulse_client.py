import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class DataImpulseAPIError(Exception):
    """DataImpulse API specific errors"""
    pass


class DataImpulseClient:
    """DataImpulse API client for social media parsing and sentiment analysis"""
    
    def __init__(self):
        self.api_key = settings.DATAIMPULSE_API_KEY
        self.base_url = settings.DATAIMPULSE_BASE_URL
        self.session = None
        self._rate_limit_delay = 0.5  # 500ms between requests
        self._last_request_time = 0
        self.timeout = settings.API_TIMEOUT
        
        if not self.api_key:
            logger.warning("DataImpulse API key not configured")
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _ensure_session(self):
        """Ensure session is available"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        self._last_request_time = time.time()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting"""
        if not self.api_key:
            raise DataImpulseAPIError("DataImpulse API key not configured")
        
        await self._ensure_session()
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return response_data
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 3))
                    logger.warning(f"DataImpulse rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self._request(method, endpoint, **kwargs)
                elif response.status == 401:
                    raise DataImpulseAPIError("Invalid DataImpulse API key")
                else:
                    error_msg = response_data.get('message', f'HTTP {response.status}')
                    raise DataImpulseAPIError(f"DataImpulse API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            raise DataImpulseAPIError("DataImpulse API request timeout")
        except aiohttp.ClientError as e:
            raise DataImpulseAPIError(f"DataImpulse client error: {str(e)}")
    
    async def search_twitter(self, query: str, limit: int = 100, 
                           time_range: str = "24h", lang: str = "en") -> List[Dict[str, Any]]:
        """Search Twitter for posts related to a token or keyword"""
        try:
            endpoint = "/v1/social/twitter/search"
            payload = {
                "query": query,
                "limit": min(limit, 500),  # API limit
                "time_range": time_range,  # 1h, 24h, 7d, 30d
                "lang": lang,
                "include_replies": False,
                "include_retweets": True,
                "sentiment_analysis": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("tweets"):
                return []
            
            tweets = []
            for tweet in response["data"]["tweets"]:
                tweet_data = {
                    "id": tweet.get("id"),
                    "text": tweet.get("text"),
                    "author": {
                        "username": tweet.get("author", {}).get("username"),
                        "name": tweet.get("author", {}).get("name"),
                        "followers_count": tweet.get("author", {}).get("followers_count"),
                        "verified": tweet.get("author", {}).get("verified", False)
                    },
                    "created_at": tweet.get("created_at"),
                    "metrics": {
                        "retweet_count": tweet.get("metrics", {}).get("retweet_count", 0),
                        "like_count": tweet.get("metrics", {}).get("like_count", 0),
                        "reply_count": tweet.get("metrics", {}).get("reply_count", 0),
                        "quote_count": tweet.get("metrics", {}).get("quote_count", 0)
                    },
                    "sentiment": {
                        "score": tweet.get("sentiment", {}).get("score"),
                        "label": tweet.get("sentiment", {}).get("label"),  # positive, negative, neutral
                        "confidence": tweet.get("sentiment", {}).get("confidence")
                    },
                    "entities": tweet.get("entities", {}),
                    "hashtags": tweet.get("hashtags", []),
                    "mentions": tweet.get("mentions", []),
                    "urls": tweet.get("urls", []),
                    "language": tweet.get("language"),
                    "platform": "twitter"
                }
                tweets.append(tweet_data)
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error searching Twitter with DataImpulse for query '{query}': {str(e)}")
            return []
    
    async def search_telegram(self, query: str, limit: int = 100, 
                            time_range: str = "24h", channels: List[str] = None) -> List[Dict[str, Any]]:
        """Search Telegram channels for posts related to a token or keyword"""
        try:
            endpoint = "/v1/social/telegram/search"
            payload = {
                "query": query,
                "limit": min(limit, 300),
                "time_range": time_range,
                "channels": channels or [],  # Specific channels to search
                "sentiment_analysis": True,
                "include_forwarded": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("messages"):
                return []
            
            messages = []
            for message in response["data"]["messages"]:
                message_data = {
                    "id": message.get("id"),
                    "text": message.get("text"),
                    "channel": {
                        "name": message.get("channel", {}).get("name"),
                        "username": message.get("channel", {}).get("username"),
                        "subscribers": message.get("channel", {}).get("subscribers"),
                        "verified": message.get("channel", {}).get("verified", False)
                    },
                    "author": {
                        "name": message.get("author", {}).get("name"),
                        "username": message.get("author", {}).get("username")
                    },
                    "created_at": message.get("created_at"),
                    "metrics": {
                        "views": message.get("metrics", {}).get("views", 0),
                        "forwards": message.get("metrics", {}).get("forwards", 0),
                        "replies": message.get("metrics", {}).get("replies", 0)
                    },
                    "sentiment": {
                        "score": message.get("sentiment", {}).get("score"),
                        "label": message.get("sentiment", {}).get("label"),
                        "confidence": message.get("sentiment", {}).get("confidence")
                    },
                    "is_forwarded": message.get("is_forwarded", False),
                    "has_media": message.get("has_media", False),
                    "hashtags": message.get("hashtags", []),
                    "mentions": message.get("mentions", []),
                    "urls": message.get("urls", []),
                    "platform": "telegram"
                }
                messages.append(message_data)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error searching Telegram with DataImpulse for query '{query}': {str(e)}")
            return []
    
    async def search_discord(self, query: str, limit: int = 100, 
                           time_range: str = "24h", servers: List[str] = None) -> List[Dict[str, Any]]:
        """Search Discord servers for posts related to a token or keyword"""
        try:
            endpoint = "/v1/social/discord/search"
            payload = {
                "query": query,
                "limit": min(limit, 200),
                "time_range": time_range,
                "servers": servers or [],  # Specific servers to search
                "sentiment_analysis": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("messages"):
                return []
            
            messages = []
            for message in response["data"]["messages"]:
                message_data = {
                    "id": message.get("id"),
                    "content": message.get("content"),
                    "server": {
                        "name": message.get("server", {}).get("name"),
                        "id": message.get("server", {}).get("id"),
                        "members": message.get("server", {}).get("members")
                    },
                    "channel": {
                        "name": message.get("channel", {}).get("name"),
                        "id": message.get("channel", {}).get("id"),
                        "type": message.get("channel", {}).get("type")
                    },
                    "author": {
                        "username": message.get("author", {}).get("username"),
                        "id": message.get("author", {}).get("id"),
                        "roles": message.get("author", {}).get("roles", [])
                    },
                    "created_at": message.get("created_at"),
                    "metrics": {
                        "reactions": message.get("metrics", {}).get("reactions", 0),
                        "replies": message.get("metrics", {}).get("replies", 0)
                    },
                    "sentiment": {
                        "score": message.get("sentiment", {}).get("score"),
                        "label": message.get("sentiment", {}).get("label"),
                        "confidence": message.get("sentiment", {}).get("confidence")
                    },
                    "has_attachments": message.get("has_attachments", False),
                    "mentions": message.get("mentions", []),
                    "platform": "discord"
                }
                messages.append(message_data)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error searching Discord with DataImpulse for query '{query}': {str(e)}")
            return []
    
    async def search_reddit(self, query: str, limit: int = 100, 
                          time_range: str = "24h", subreddits: List[str] = None) -> List[Dict[str, Any]]:
        """Search Reddit for posts related to a token or keyword"""
        try:
            endpoint = "/v1/social/reddit/search"
            payload = {
                "query": query,
                "limit": min(limit, 250),
                "time_range": time_range,
                "subreddits": subreddits or ["CryptoMoonShots", "cryptocurrency", "solana", "defi"],
                "sentiment_analysis": True,
                "include_comments": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("posts"):
                return []
            
            posts = []
            for post in response["data"]["posts"]:
                post_data = {
                    "id": post.get("id"),
                    "title": post.get("title"),
                    "text": post.get("text"),
                    "subreddit": post.get("subreddit"),
                    "author": {
                        "username": post.get("author", {}).get("username"),
                        "karma": post.get("author", {}).get("karma"),
                        "account_age": post.get("author", {}).get("account_age")
                    },
                    "created_at": post.get("created_at"),
                    "metrics": {
                        "upvotes": post.get("metrics", {}).get("upvotes", 0),
                        "downvotes": post.get("metrics", {}).get("downvotes", 0),
                        "comments": post.get("metrics", {}).get("comments", 0),
                        "awards": post.get("metrics", {}).get("awards", 0)
                    },
                    "sentiment": {
                        "score": post.get("sentiment", {}).get("score"),
                        "label": post.get("sentiment", {}).get("label"),
                        "confidence": post.get("sentiment", {}).get("confidence")
                    },
                    "flair": post.get("flair"),
                    "is_pinned": post.get("is_pinned", False),
                    "is_nsfw": post.get("is_nsfw", False),
                    "url": post.get("url"),
                    "platform": "reddit"
                }
                posts.append(post_data)
            
            return posts
            
        except Exception as e:
            logger.error(f"Error searching Reddit with DataImpulse for query '{query}': {str(e)}")
            return []
    
    async def get_sentiment_analysis(self, texts: List[str], language: str = "en") -> List[Dict[str, Any]]:
        """Get sentiment analysis for a list of texts"""
        try:
            endpoint = "/v1/analytics/sentiment"
            payload = {
                "texts": texts[:100],  # Limit to 100 texts per request
                "language": language,
                "detailed": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("results"):
                return []
            
            results = []
            for result in response["data"]["results"]:
                sentiment_data = {
                    "text": result.get("text"),
                    "sentiment": {
                        "score": result.get("sentiment", {}).get("score"),  # -1 to 1
                        "label": result.get("sentiment", {}).get("label"),  # positive, negative, neutral
                        "confidence": result.get("sentiment", {}).get("confidence")
                    },
                    "emotions": result.get("emotions", {}),  # joy, anger, fear, etc.
                    "keywords": result.get("keywords", []),
                    "language": result.get("language")
                }
                results.append(sentiment_data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting sentiment analysis from DataImpulse: {str(e)}")
            return []
    
    async def get_trending_topics(self, platform: str = "all", time_range: str = "24h", 
                                 category: str = "crypto") -> List[Dict[str, Any]]:
        """Get trending topics related to crypto"""
        try:
            endpoint = "/v1/analytics/trending"
            params = {
                "platform": platform,  # twitter, telegram, discord, reddit, all
                "time_range": time_range,
                "category": category,
                "limit": 50
            }
            
            response = await self._request("GET", endpoint, params=params)
            
            if not response.get("data") or not response["data"].get("topics"):
                return []
            
            topics = []
            for topic in response["data"]["topics"]:
                topic_data = {
                    "keyword": topic.get("keyword"),
                    "mention_count": topic.get("mention_count"),
                    "sentiment_score": topic.get("sentiment_score"),
                    "growth_rate": topic.get("growth_rate"),
                    "platforms": topic.get("platforms", []),
                    "related_tokens": topic.get("related_tokens", []),
                    "top_posts": topic.get("top_posts", [])
                }
                topics.append(topic_data)
            
            return topics
            
        except Exception as e:
            logger.warning(f"Error getting trending topics from DataImpulse: {str(e)}")
            return []
    
    async def get_influencer_mentions(self, query: str, min_followers: int = 1000, 
                                    time_range: str = "24h") -> List[Dict[str, Any]]:
        """Get mentions from crypto influencers"""
        try:
            endpoint = "/v1/social/influencers/mentions"
            payload = {
                "query": query,
                "min_followers": min_followers,
                "time_range": time_range,
                "platforms": ["twitter", "telegram"],
                "verified_only": False
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data") or not response["data"].get("mentions"):
                return []
            
            mentions = []
            for mention in response["data"]["mentions"]:
                mention_data = {
                    "id": mention.get("id"),
                    "text": mention.get("text"),
                    "platform": mention.get("platform"),
                    "influencer": {
                        "username": mention.get("influencer", {}).get("username"),
                        "name": mention.get("influencer", {}).get("name"),
                        "followers": mention.get("influencer", {}).get("followers"),
                        "verified": mention.get("influencer", {}).get("verified", False),
                        "influence_score": mention.get("influencer", {}).get("influence_score")
                    },
                    "created_at": mention.get("created_at"),
                    "metrics": mention.get("metrics", {}),
                    "sentiment": mention.get("sentiment", {}),
                    "reach_estimate": mention.get("reach_estimate"),
                    "engagement_rate": mention.get("engagement_rate")
                }
                mentions.append(mention_data)
            
            return mentions
            
        except Exception as e:
            logger.warning(f"Error getting influencer mentions from DataImpulse: {str(e)}")
            return []
    
    async def analyze_token_buzz(self, token_symbol: str, token_name: str = None, 
                                time_range: str = "24h") -> Dict[str, Any]:
        """Comprehensive analysis of token social buzz"""
        try:
            search_queries = [token_symbol]
            if token_name:
                search_queries.append(token_name)
            
            # Search across all platforms
            all_posts = []
            for query in search_queries:
                # Parallel search across platforms
                twitter_task = self.search_twitter(query, 50, time_range)
                telegram_task = self.search_telegram(query, 50, time_range)
                reddit_task = self.search_reddit(query, 30, time_range)
                
                twitter_posts, telegram_posts, reddit_posts = await asyncio.gather(
                    twitter_task, telegram_task, reddit_task,
                    return_exceptions=True
                )
                
                # Handle exceptions
                if not isinstance(twitter_posts, Exception):
                    all_posts.extend(twitter_posts)
                if not isinstance(telegram_posts, Exception):
                    all_posts.extend(telegram_posts)
                if not isinstance(reddit_posts, Exception):
                    all_posts.extend(reddit_posts)
            
            if not all_posts:
                return {
                    "token_symbol": token_symbol,
                    "analysis_period": time_range,
                    "total_mentions": 0,
                    "platforms": {},
                    "sentiment": {},
                    "trending_score": 0,
                    "key_metrics": {}
                }
            
            # Analyze the collected data
            analysis = self._analyze_social_data(all_posts, token_symbol)
            analysis["token_symbol"] = token_symbol
            analysis["analysis_period"] = time_range
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing token buzz for {token_symbol}: {str(e)}")
            return {
                "token_symbol": token_symbol,
                "error": str(e),
                "total_mentions": 0
            }
    
    def _analyze_social_data(self, posts: List[Dict[str, Any]], token_symbol: str) -> Dict[str, Any]:
        """Analyze collected social media data"""
        if not posts:
            return {}
        
        # Platform breakdown
        platforms = {}
        for post in posts:
            platform = post.get("platform", "unknown")
            if platform not in platforms:
                platforms[platform] = {
                    "count": 0,
                    "total_engagement": 0,
                    "avg_sentiment": 0,
                    "top_posts": []
                }
            platforms[platform]["count"] += 1
            
            # Calculate engagement
            metrics = post.get("metrics", {})
            if platform == "twitter":
                engagement = metrics.get("like_count", 0) + metrics.get("retweet_count", 0)
            elif platform == "telegram":
                engagement = metrics.get("views", 0) + metrics.get("forwards", 0)
            elif platform == "reddit":
                engagement = metrics.get("upvotes", 0) + metrics.get("comments", 0)
            else:
                engagement = 0
            
            platforms[platform]["total_engagement"] += engagement
            
            # Add sentiment
            sentiment_score = post.get("sentiment", {}).get("score", 0)
            platforms[platform]["avg_sentiment"] += sentiment_score
            
            # Track top posts
            if engagement > 0:
                platforms[platform]["top_posts"].append({
                    "text": post.get("text", post.get("content", ""))[:200],
                    "engagement": engagement,
                    "sentiment": sentiment_score,
                    "created_at": post.get("created_at")
                })
        
        # Calculate averages and sort top posts
        for platform_data in platforms.values():
            if platform_data["count"] > 0:
                platform_data["avg_sentiment"] /= platform_data["count"]
                platform_data["avg_engagement"] = platform_data["total_engagement"] / platform_data["count"]
                platform_data["top_posts"] = sorted(
                    platform_data["top_posts"], 
                    key=lambda x: x["engagement"], 
                    reverse=True
                )[:5]
        
        # Overall sentiment analysis
        sentiments = [post.get("sentiment", {}).get("score", 0) for post in posts if post.get("sentiment")]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
        
        positive_count = len([s for s in sentiments if s > 0.1])
        negative_count = len([s for s in sentiments if s < -0.1])
        neutral_count = len(sentiments) - positive_count - negative_count
        
        # Calculate trending score
        total_engagement = sum(platforms[p]["total_engagement"] for p in platforms)
        mention_velocity = len(posts)  # Posts per time period
        sentiment_boost = max(0, avg_sentiment) * 10  # Positive sentiment boost
        
        trending_score = min(100, (mention_velocity * 2) + (total_engagement / 100) + sentiment_boost)
        
        # Key metrics
        key_metrics = {
            "mention_velocity": mention_velocity,
            "total_engagement": total_engagement,
            "unique_authors": len(set(post.get("author", {}).get("username", "") for post in posts)),
            "viral_potential": trending_score,
            "sentiment_distribution": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count
            }
        }
        
        return {
            "total_mentions": len(posts),
            "platforms": platforms,
            "sentiment": {
                "average_score": avg_sentiment,
                "label": "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral",
                "distribution": {
                    "positive": positive_count,
                    "negative": negative_count,
                    "neutral": neutral_count
                }
            },
            "trending_score": round(trending_score, 2),
            "key_metrics": key_metrics,
            "analysis_timestamp": int(time.time())
        }
    
    async def get_meme_analysis(self, token_symbol: str, time_range: str = "24h") -> Dict[str, Any]:
        """Analyze meme potential and viral content"""
        try:
            endpoint = "/v1/analytics/memes"
            payload = {
                "token": token_symbol,
                "time_range": time_range,
                "include_images": True,
                "include_videos": True
            }
            
            response = await self._request("POST", endpoint, json=payload)
            
            if not response.get("data"):
                return {}
            
            data = response["data"]
            meme_analysis = {
                "token_symbol": token_symbol,
                "meme_score": data.get("meme_score"),  # 0-100
                "viral_potential": data.get("viral_potential"),
                "trending_memes": data.get("trending_memes", []),
                "popular_hashtags": data.get("popular_hashtags", []),
                "meme_categories": data.get("meme_categories", []),
                "viral_content": data.get("viral_content", []),
                "community_engagement": data.get("community_engagement", {}),
                "influencer_adoption": data.get("influencer_adoption", [])
            }
            
            return meme_analysis
            
        except Exception as e:
            logger.warning(f"Error getting meme analysis for {token_symbol}: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check DataImpulse API health"""
        try:
            start_time = time.time()
            
            # Simple API test
            endpoint = "/v1/health"
            response = await self._request("GET", endpoint)
            
            response_time = time.time() - start_time
            
            return {
                "healthy": True,
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url,
                "response_time": response_time,
                "status": response.get("status", "operational")
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "base_url": self.base_url
            }


# Convenience functions
async def get_dataimpulse_client() -> DataImpulseClient:
    """Get configured DataImpulse client"""
    return DataImpulseClient()


async def check_dataimpulse_health() -> Dict[str, Any]:
    """Check DataImpulse service health"""
    async with DataImpulseClient() as client:
        return await client.health_check()