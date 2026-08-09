"""
llm_service.py

This is the centralized LLM integration layer for The Interview Agent.
It supports:
  1. Google Gemini (via google-genai / standard REST)
  2. Anthropic Claude (via anthropic SDK)
  3. OpenAI / OpenRouter / Groq (via openai SDK)
  4. Mock / Offline Mode (intelligent rule-based responses for tests/demo)

Configuration is loaded from environment variables (.env).
"""

import json
import os
import re
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class LLMServiceError(RuntimeError):
    """Raised when an LLM call fails or returns unparseable data."""


def _get_provider() -> str:
    """Returns the configured LLM provider in lowercase (default: gemini if GEMINI_API_KEY exists, else anthropic, or mock)."""
    explicit = os.getenv("LLM_PROVIDER")
    if explicit:
        return explicit.lower().strip()
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "mock"


def _get_model(provider: str) -> str:
    """Returns default model name for the given provider."""
    env_model = os.getenv("LLM_MODEL")
    if env_model:
        return env_model
    if provider in ("gemini", "google"):
        return "gemini-2.0-flash"
    if provider == "anthropic":
        return "claude-3-5-sonnet-latest"
    if provider == "openai":
        return "gpt-4o-mini"
    return "mock-model"


def _call_gemini(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> str:
    """Call Google Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise LLMServiceError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=0.7,
            ),
        )
        return response.text or ""
    except ImportError:
        # Fallback to direct HTTP call if google-genai package is not yet installed
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
        }
        resp = httpx.post(url, json=payload, timeout=45.0)
        if resp.status_code != 200:
            raise LLMServiceError(f"Gemini API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMServiceError("Gemini returned empty candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    except Exception as exc:
        raise LLMServiceError(f"Gemini API error: {exc}") from exc


def _call_anthropic(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> str:
    """Call Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMServiceError("ANTHROPIC_API_KEY is not set.")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
    except ImportError as exc:
        raise LLMServiceError("Anthropic SDK is not installed.") from exc
    except Exception as exc:
        raise LLMServiceError(f"Anthropic API error: {exc}") from exc


def _call_openai(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> str:
    """Call OpenAI / OpenRouter / Groq API."""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not api_key:
        raise LLMServiceError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except ImportError as exc:
        raise LLMServiceError("OpenAI SDK is not installed.") from exc
    except Exception as exc:
        raise LLMServiceError(f"OpenAI API error: {exc}") from exc


def _call_mock(user_prompt: str) -> str:
    """
    Intelligent mock responder for offline execution, automated testing,
    and fast demoing when no API keys are available.
    """
    lower = user_prompt.lower()

    # 1. Answer evaluation prompt
    if "you are evaluating a candidate's answer" in lower or "missing_concepts" in lower:
        # Determine score based on answer content length and keywords
        if "idk" in lower or "don't know" in lower or "not sure" in lower or len(lower) < 20:
            return json.dumps({
                "score": 3,
                "understanding": "weak",
                "technical_correctness": "partially_correct",
                "strengths": ["Honest response about uncertainty"],
                "missing_concepts": ["Core theoretical mechanism", "Practical architectural trade-offs"],
                "follow_up_needed": True,
                "recommended_action": "CLARIFY",
            })
        return json.dumps({
            "score": 8,
            "understanding": "strong",
            "technical_correctness": "correct",
            "strengths": ["Clear technical explanation", "Good coverage of key concepts"],
            "missing_concepts": [],
            "follow_up_needed": False,
            "recommended_action": "NEW_TOPIC",
        })

    # 2. Follow-up question prompt
    if "follow-up question" in lower or "their answer was missing or unclear on" in lower:
        day_match = re.search(r"day\s*(\d+)", lower)
        day_num = int(day_match.group(1)) if day_match else 7
        return json.dumps({
            "question": "Could you elaborate on how you handle edge cases and optimize latency in that scenario?",
            "day": day_num,
            "level": 3,
            "topic": f"Day {day_num} Deep Dive",
        })

    # 3. Question generation prompt
    if "write the next interview question" in lower or "curriculum day to base this question on" in lower:
        day_match = re.search(r"day\s*(\d+)", lower)
        day_num = int(day_match.group(1)) if day_match else 7
        
        sample_questions = {
            7: "How do embedding vector dimensions impact search accuracy versus computational cost in dense retrieval?",
            8: "What are the primary differences between HNSW and IVF indexing algorithms in vector databases?",
            10: "In a RAG pipeline, how would you implement re-ranking to improve top-k precision?",
            12: "How do you systematically prevent prompt injection in multi-tenant LLM applications?",
            13: "How does function calling handle schema validation errors when an LLM generates invalid JSON arguments?",
            16: "What strategies do you use to manage conversation state across asynchronous chat sessions?",
            18: "How do Server-Sent Events (SSE) differ from WebSockets for streaming token responses to clients?",
            22: "In a multi-agent system, how do you handle deadlock or infinite loops between collaborative agents?",
            23: "What is Model Context Protocol (MCP) and how does it standardize tool definitions across models?",
            28: "How do you configure horizontal pod autoscaling for GPU-accelerated LLM inference workloads in Kubernetes?",
            29: "What metrics are most critical to monitor for detecting LLM hallucination and latency drift in production?",
            31: "Can you walk through the system architecture of your AI capstone project and the key trade-offs you made?",
        }
        q_text = sample_questions.get(
            day_num,
            f"Can you explain the architectural principles and practical implementation details of Day {day_num}?"
        )
        return json.dumps({
            "question": q_text,
            "day": day_num,
            "level": 3,
            "topic": f"Day {day_num} Technical Assessment",
        })

    # 4. Final feedback prompt
    if "write the final interview feedback" in lower or "final feedback" in lower:
        return json.dumps({
            "summary": "The candidate demonstrated solid technical understanding across multiple AI engineering domains, articulating concepts clearly with strong practical intuition.",
            "strengths": [
                "Strong grasp of vector search indexing and embedding retrieval mechanisms",
                "Clear explanation of multi-agent coordination patterns and API integration",
                "Practical understanding of deployment trade-offs in production systems",
            ],
            "gaps": [
                "Could deepen understanding of advanced observability and drift detection metrics",
                "Opportunities to explore more nuanced fine-tuning vs. RAG latency trade-offs",
            ],
            "next": [
                "Implement end-to-end telemetry and evaluation benchmarks using Ragas or TruLens",
                "Experiment with MCP server implementations for custom enterprise tool integration",
                "Practice architectural system design for high-throughput streaming AI backends",
            ],
        })

    return "Thank you. Let's continue to the next technical topic."


def generate_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """
    Send prompt to configured LLM provider and return response text.
    """
    provider = _get_provider()
    target_model = model or _get_model(provider)

    try:
        if provider in ("gemini", "google"):
            return _call_gemini(system_prompt, user_prompt, target_model, max_tokens)
        if provider == "anthropic":
            return _call_anthropic(system_prompt, user_prompt, target_model, max_tokens)
        if provider in ("openai", "openrouter", "groq"):
            return _call_openai(system_prompt, user_prompt, target_model, max_tokens)
        if provider in ("mock", "demo"):
            return _call_mock(user_prompt)
        raise LLMServiceError(f"Unsupported LLM_PROVIDER: '{provider}'")
    except Exception as exc:
        if os.getenv("MOCK_FALLBACK_ON_ERROR", "true").lower() == "true":
            print(f"[llm_service] Falling back to Mock engine due to provider error: {exc}")
            return _call_mock(user_prompt)
        raise


def generate_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """
    Send prompt and parse LLM response as JSON.
    """
    raw = generate_text(system_prompt, user_prompt, model=model, max_tokens=max_tokens)
    return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Turn a raw LLM text reply into a dict, tolerating common formatting and markdown fences."""
    cleaned = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise LLMServiceError(
                f"LLM did not return valid JSON. Raw reply started with: {raw[:300]!r}"
            ) from exc
