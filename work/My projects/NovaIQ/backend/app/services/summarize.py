"""
Summarization service for generating insights from articles.

Uses OpenAI API to extract key insights with bullets and citations.
"""
from typing import Optional
import json

from app.deps import get_openai_client
from app.db.models import Article


async def summarize_articles(
    articles: list[Article],
    *,
    model: str = "gpt-4o-mini"
) -> Optional[dict[str, any]]:
    """
    Generate insight summary from multiple articles.
    
    Args:
        articles: List of articles to summarize
        model: OpenAI model to use
    
    Returns:
        Dict with: title, summary, bullets, confidence
        None if OpenAI not available
    """
    client = get_openai_client()
    if not client or not articles:
        return None
    
    # Build context from articles
    context = "\n\n".join([
        f"Article {i+1}: {a.title}\n"
        f"Source: {a.url}\n"
        f"Content: {a.content[:1000]}..."
        for i, a in enumerate(articles[:10])  # Max 10 articles
    ])
    
    # System prompt for insight extraction
    system_prompt = """You are an AI research analyst. Extract key insights from the provided articles.

Return a JSON object with:
{
  "title": "Brief, engaging title for the insight",
  "summary": "2-3 sentence summary of the main insight",
  "bullets": ["bullet point 1", "bullet point 2", ...],  // 3-5 key points
  "confidence": 0.85  // Your confidence in this insight (0.0-1.0)
}

Focus on:
- Novel findings or trends
- Practical implications
- Connections between articles
"""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Articles:\n\n{context}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Validate required fields
        required = ["title", "summary", "bullets", "confidence"]
        if not all(k in result for k in required):
            return None
        
        return result
        
    except Exception as e:
        print(f"Summarization error: {e}")
        return None


async def summarize_single_article(
    article: Article,
    *,
    model: str = "gpt-4o-mini"
) -> Optional[dict[str, any]]:
    """
    Generate a concise summary of a single article.
    
    Args:
        article: Article to summarize
        model: OpenAI model to use
    
    Returns:
        Dict with: summary, key_points
    """
    client = get_openai_client()
    if not client:
        return None
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize this article in 2-3 sentences. "
                               "Extract 3 key points as a JSON array."
                },
                {
                    "role": "user",
                    "content": f"Title: {article.title}\n\n{article.content}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Article summarization error: {e}")
        return None
