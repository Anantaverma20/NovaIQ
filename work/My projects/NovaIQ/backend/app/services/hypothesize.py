"""
Hypothesis generation service.

Generates testable hypotheses from insights using OpenAI.
"""
from typing import Optional
import json

from app.deps import get_openai_client
from app.db.models import InsightDB


async def generate_hypotheses(
    insight: InsightDB,
    *,
    model: str = "gpt-4o-mini",
    num_hypotheses: int = 3
) -> list[dict[str, any]]:
    """
    Generate testable hypotheses from an insight.
    
    Args:
        insight: Insight to generate hypotheses from
        model: OpenAI model to use
        num_hypotheses: Number of hypotheses to generate (2-5)
    
    Returns:
        List of hypothesis dicts with: hypothesis, rationale, confidence
        Empty list if OpenAI not available
    """
    client = get_openai_client()
    if not client:
        return []
    
    # Prepare insight context
    bullets = json.loads(insight.bullets) if insight.bullets else []
    bullets_text = "\n".join([f"- {b}" for b in bullets])
    
    context = f"""Insight: {insight.title}

Summary: {insight.summary}

Key Points:
{bullets_text}
"""
    
    # System prompt for hypothesis generation
    system_prompt = f"""You are a research scientist generating testable hypotheses.

Given an insight, generate {num_hypotheses} testable hypotheses that could be investigated further.

Return a JSON object with:
{{
  "hypotheses": [
    {{
      "hypothesis": "Clear, testable hypothesis statement",
      "rationale": "Why this hypothesis is worth investigating",
      "confidence": 0.75  // Your confidence this is a good hypothesis (0.0-1.0)
    }},
    ...
  ]
}}

Each hypothesis should be:
- Specific and testable
- Based on the insight provided
- Actionable for further research
"""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            response_format={"type": "json_object"},
            temperature=0.8,  # Higher temp for creative hypotheses
        )
        
        result = json.loads(response.choices[0].message.content)
        hypotheses = result.get("hypotheses", [])
        
        # Validate each hypothesis
        valid_hypotheses = []
        for h in hypotheses:
            if all(k in h for k in ["hypothesis", "rationale", "confidence"]):
                valid_hypotheses.append(h)
        
        return valid_hypotheses[:num_hypotheses]  # Cap at requested number
        
    except Exception as e:
        print(f"Hypothesis generation error: {e}")
        return []


async def evaluate_hypothesis(
    hypothesis: str,
    evidence: list[str],
    *,
    model: str = "gpt-4o-mini"
) -> Optional[dict[str, any]]:
    """
    Evaluate a hypothesis against provided evidence.
    
    Args:
        hypothesis: Hypothesis to evaluate
        evidence: List of evidence statements
        model: OpenAI model to use
    
    Returns:
        Dict with: support_score, reasoning, next_steps
    """
    client = get_openai_client()
    if not client or not evidence:
        return None
    
    evidence_text = "\n".join([f"{i+1}. {e}" for i, e in enumerate(evidence)])
    
    prompt = f"""Hypothesis: {hypothesis}

Evidence:
{evidence_text}

Evaluate how well the evidence supports this hypothesis.

Return JSON:
{{
  "support_score": 0.65,  // 0.0 (no support) to 1.0 (strong support)
  "reasoning": "Brief explanation of the evaluation",
  "next_steps": ["Suggestion 1", "Suggestion 2", ...]  // What to investigate next
}}
"""
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a research analyst evaluating hypotheses."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Hypothesis evaluation error: {e}")
        return None
