"""
llm_service.py

Unified, multi-provider LLM calling service supporting:
  - Google Gemini (google-genai / gemini-2.0-flash / gemini-1.5-flash)
  - Anthropic Claude (anthropic / claude-3-5-sonnet / claude-3-haiku)
  - OpenAI (openai / gpt-4o / gpt-4o-mini / Groq / OpenRouter)
  - Smart Offline Mock Fallback (with rich grounded questions for all 31 cohort days)
"""

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Complete grounded question pool covering all 31 days of the cohort curriculum
CURRICULUM_QUESTIONS = {
    1: {
        "title": "VS Code & Python Environment Setup",
        1: "How do you create and activate an isolated Python virtual environment (.venv), and why is it essential?",
        2: "How do VS Code extensions like Pylance and the Python debugger assist in identifying type mismatches and runtime exceptions?",
        3: "When configuring a development environment for AI applications, how do you manage dependency pinning with requirements.txt or pip-tools?",
        4: "How do you troubleshoot path resolution and virtual environment interpreter conflicts when running Python scripts inside VS Code terminal?",
        5: "Describe an optimal cross-platform setup for Python AI engineering that ensures reproducible build environments across team members."
    },
    2: {
        "title": "Local LLM & AI Coding Assistant Setup",
        1: "What is Ollama and how does it enable running open-weight LLMs locally on your workstation?",
        2: "How do local coding assistants like Cline or GitHub Copilot communicate with local inference runtimes?",
        3: "How do you benchmark local inference latency and token throughput when running quantized models like Qwen2.5-Coder?",
        4: "What are the memory and VRAM trade-offs between 4-bit, 8-bit, and 16-bit model quantizations during local inference?",
        5: "How would you design a secure, offline-first development pipeline using local LLMs for proprietary enterprise codebases?"
    },
    3: {
        "title": "First AI Project, React Frontend & GitHub",
        1: "How do you scaffold a basic FastAPI backend that communicates with a local Ollama model?",
        2: "How does a React frontend built with Vite asynchronously fetch responses from a Python API?",
        3: "How do you structure Git branching and GitHub repository workflows when collaborating on full-stack AI projects?",
        4: "How do you handle CORS and request timeout errors when connecting a Vite frontend to an Ollama-backed FastAPI service?",
        5: "Design the end-to-end architecture of a local full-stack chatbot with graceful degradation when the inference backend is unreachable."
    },
    4: {
        "title": "Reading & Processing Structured Data",
        1: "What are the primary differences between Pandas and Polars when parsing tabular CSV and JSON datasets?",
        2: "How do you validate structured JSON inputs using Pydantic models before passing them to an analytics pipeline?",
        3: "How do you handle schema drift and missing categorical values when loading structured data for embedding generation?",
        4: "How do you optimize memory consumption when processing multi-gigabyte structured datasets using chunked streaming in Python?",
        5: "Design an automated structured data ingestion engine with strict validation, error quarantining, and schema evolution support."
    },
    5: {
        "title": "Reading & Processing Unstructured Data",
        1: "What strategies do you use to extract clean text from messy unstructured documents like PDFs, DOCX, and HTML?",
        2: "Why is text chunking necessary before generating vector embeddings, and what are the main chunking strategies?",
        3: "How do you balance chunk size versus chunk overlap to prevent cutting off key context in RAG pipelines?",
        4: "How do you handle multi-column layouts, tables, and OCR artifacts during document parsing?",
        5: "Architect an enterprise unstructured document ingestion pipeline that preserves document hierarchy and semantic structure."
    },
    6: {
        "title": "Data Cleaning & Preprocessing",
        1: "What common text preprocessing steps (such as deduplication, whitespace stripping, and regex normalization) are applied before indexing?",
        2: "Why can over-aggressive text normalization (e.g. lowercasing or stopword removal) harm semantic search quality?",
        3: "How do you identify and remove duplicate or near-duplicate passages across a large corpus using MinHash or embeddings?",
        4: "How do you sanitize sensitive PII data (emails, credit cards, SSNs) before indexing text into a search database?",
        5: "Design a scalable preprocessing pipeline with data provenance tracking and quality validation gates."
    },
    7: {
        "title": "Embeddings Explained",
        1: "What is a vector embedding, and how does it capture semantic meaning compared to keyword-based search?",
        2: "How does cosine similarity measure semantic closeness between two embedding vectors compared to Euclidean distance?",
        3: "How do embedding vector dimensions impact search accuracy versus computational cost in dense retrieval?",
        4: "How do you handle domain mismatch when using general-purpose embedding models on specialized medical or legal text?",
        5: "Design a hybrid embedding retrieval architecture combining sparse BM25 representations with dense vector embeddings."
    },
    8: {
        "title": "Vector Databases Overview",
        1: "What is the primary role of a vector database like Chroma, Qdrant, or Pinecone in modern AI architectures?",
        2: "What are the core differences between Approximate Nearest Neighbor (ANN) search and exact k-NN search?",
        3: "What are the primary differences between HNSW (Hierarchical Navigable Small World) and IVF indexing algorithms?",
        4: "How do you configure HNSW parameters (M, ef_construction, ef_search) to balance memory footprint and recall rate?",
        5: "Architect a distributed vector database deployment capable of handling millions of vectors with sub-20ms query latency."
    },
    9: {
        "title": "Vector Search in Practice",
        1: "How do metadata filters work in vector databases, and why are they useful during similarity search?",
        2: "What is the difference between pre-filtering and post-filtering when executing hybrid metadata-vector queries?",
        3: "How do you implement namespace partitioning and multi-tenancy in vector search applications?",
        4: "How do you handle index updates and deletions without degrading ongoing query throughput?",
        5: "Design a multi-tenant vector search system with strict access control and real-time document indexing."
    },
    10: {
        "title": "Retrieval & Matching Engine",
        1: "What is the difference between bi-encoders and cross-encoders in information retrieval pipelines?",
        2: "In a RAG pipeline, how does a re-ranker model improve top-k precision after initial vector retrieval?",
        3: "How do you balance retrieval latency against ranking precision when combining dense search with a cross-encoder re-ranker?",
        4: "How do you evaluate retrieval precision@k and Mean Reciprocal Rank (MRR) on a domain-specific query dataset?",
        5: "Architect a two-stage retrieval and matching engine optimized for high-throughput question-answering systems."
    },
    11: {
        "title": "RAG End-to-End & LLM API Basics",
        1: "Can you explain the end-to-end lifecycle of a Retrieval-Augmented Generation (RAG) query from user prompt to final answer?",
        2: "How do you format the prompt context to prevent the LLM from hallucinating answers outside the retrieved documents?",
        3: "How do you manage context window token limits when retrieved documents exceed the maximum context length?",
        4: "What techniques do you use to mitigate the 'lost in the middle' phenomenon in large context windows?",
        5: "Design a production RAG system with citations, source attribution, and real-time hallucination detection."
    },
    12: {
        "title": "Prompt Engineering Fundamentals",
        1: "What are the differences between zero-shot, few-shot, and chain-of-thought prompting?",
        2: "How does system prompt design establish behavioral guardrails and output constraints for conversational agents?",
        3: "How do you systematically prevent prompt injection and jailbreaking in multi-tenant LLM applications?",
        4: "How do you evaluate the robustness and consistency of prompts across different model versions?",
        5: "Design an enterprise prompt management and versioning platform with automated regression testing."
    },
    13: {
        "title": "Function Calling & Structured Outputs",
        1: "What is function calling (tool calling), and how does an LLM emit structured JSON arguments to invoke external APIs?",
        2: "How does JSON Schema validation guarantee type safety when parsing LLM function calling outputs?",
        3: "How does an agent handle schema validation errors or missing required arguments when an LLM outputs malformed JSON?",
        4: "How do you handle multi-tool selection and parallel tool execution in complex agent workflows?",
        5: "Architect a resilient function calling gateway with rate limiting, sandboxed execution, and automatic retry loops."
    },
    14: {
        "title": "Fine-Tuning: Concepts & When to Use It",
        1: "When should an engineering team choose fine-tuning over Retrieval-Augmented Generation (RAG)?",
        2: "What are the dataset formatting and preparation requirements when creating instruction-tuning datasets?",
        3: "How do you measure catastrophic forgetting and evaluate whether fine-tuning preserved general model capabilities?",
        4: "What are the computational cost and latency trade-offs between hosting a fine-tuned model versus prompting a frontier foundation model?",
        5: "Design a decision framework and evaluation pipeline for determining when to transition from RAG to parameter-efficient fine-tuning."
    },
    15: {
        "title": "Fine-Tuning: Hands-On with LoRA & QLoRA",
        1: "What is Low-Rank Adaptation (LoRA) and how does it reduce the number of trainable parameters during fine-tuning?",
        2: "How does QLoRA combine 4-bit NormalFloat quantization with low-rank adapter matrices to enable fine-tuning on consumer GPUs?",
        3: "How do you tune LoRA rank (r), alpha, and target modules to optimize training stability and convergence?",
        4: "How do you merge LoRA adapter weights back into base model weights for zero-latency-overhead production deployment?",
        5: "Architect an automated distributed fine-tuning pipeline with checkpointing, loss tracking, and evaluation harness integration."
    },
    16: {
        "title": "Chatbot Backend & API Integration",
        1: "How do you design an asynchronous FastAPI backend for managing multi-turn conversational chat sessions?",
        2: "What is the purpose of session identifiers (sessionId) in decoupling client connection state from backend inference?",
        3: "How do you handle client disconnects, timeouts, and rate limits in high-concurrency conversational APIs?",
        4: "How do you manage database connection pools and background tasks when processing long-running AI requests?",
        5: "Design a fault-tolerant conversational API architecture supporting thousands of concurrent users with zero session loss."
    },
    17: {
        "title": "Chatbot Frontend Development",
        1: "How do you manage client-side state transitions (such as typing indicators, auto-scroll, and message histories) in chat interfaces?",
        2: "What are the accessibility (a11y) considerations when building live-updating conversational transcripts in HTML/CSS?",
        3: "How do you prevent UI stutter and maintain smooth 60fps rendering during fast text rendering or token streaming?",
        4: "How do you implement optimistic UI updates and error rollback states in modern web applications?",
        5: "Design a modular frontend architecture with separation between API client, state manager, and rendering views."
    },
    18: {
        "title": "Streaming Responses",
        1: "How do Server-Sent Events (SSE) differ from WebSockets for streaming token-by-token LLM responses to web browsers?",
        2: "Why is chunked transfer encoding beneficial for perceived latency in conversational user experiences?",
        3: "How do you handle network reconnection and buffer reconsolidation when a streaming SSE connection drops mid-sentence?",
        4: "How do you parse partial JSON fragments when streaming structured outputs or tool execution events?",
        5: "Architect a resilient streaming proxy layer with backpressure management and connection multiplexing."
    },
    19: {
        "title": "Conversation State & Message History",
        1: "How do you structure conversation message histories (system, user, assistant, tool) for multi-turn LLM contexts?",
        2: "What strategies do you use to prune or summarize message history when approaching token window limits?",
        3: "How do you ensure deterministic session recovery across server restarts without maintaining state in memory?",
        4: "How do you separate short-term conversational context from long-term user profile memory in agent architectures?",
        5: "Design a high-throughput session state caching layer using Redis with configurable TTL and compaction policies."
    },
    20: {
        "title": "Conversation Memory & Context Management",
        1: "What are the differences between buffer memory, summary memory, and vector-backed conversation memory?",
        2: "How does an agent retrieve relevant historical conversation turns using semantic search over past dialogues?",
        3: "How do you prevent hallucinations when injecting summarized historical context into the current prompt?",
        4: "What are the token cost and latency implications of running real-time summarizers on active chat conversations?",
        5: "Design a multi-tiered conversation memory hierarchy combining immediate sliding window memory with persistent semantic memory."
    },
    21: {
        "title": "LangChain Agents",
        1: "How does the ReAct (Reasoning + Acting) prompting paradigm empower LLMs to solve multi-step problems with tools?",
        2: "What is an agent executor loop, and how does it parse thought, action, and observation steps?",
        3: "How do you prevent infinite loops or tool execution runaway when an agent struggles to resolve an intermediate step?",
        4: "How do you design custom LangChain tool wrappers with strict input validation and descriptive docstrings?",
        5: "Architect a production agent system with deterministic fallback pathways when tool executions fail."
    },
    22: {
        "title": "Multi-Agent Orchestration",
        1: "What is the supervisor pattern in multi-agent systems, and how does it delegate tasks among specialized worker agents?",
        2: "How do specialized agents pass intermediate state and execution artifacts during multi-step handoffs?",
        3: "In a multi-agent system, how do you handle deadlock, race conditions, or conflicting recommendations between agents?",
        4: "How do you debug and trace execution flow across distributed, asynchronous agent graphs?",
        5: "Design a resilient multi-agent architecture with a coordinator, specialized domain agents, and a human-in-the-loop review gate."
    },
    23: {
        "title": "Model Context Protocol (MCP)",
        1: "What is Model Context Protocol (MCP), and how does it standardize tool definitions and resource access across AI models?",
        2: "What is the difference between MCP clients, MCP servers, and MCP resources?",
        3: "How does MCP improve security and modularity compared to hardcoding API client libraries inside prompt templates?",
        4: "How do you implement an MCP server in Python exposing database queries and filesystem operations to an AI agent?",
        5: "Design an enterprise MCP ecosystem allowing different LLM clients to securely query internal microservices via standardized protocols."
    },
    24: {
        "title": "Real-World MCP Tools & Integrations",
        1: "How do you configure authentication, authorization, and scoped permissions when exposing internal tools through MCP servers?",
        2: "How do you handle schema versioning and backwards compatibility when updating MCP tool interfaces?",
        3: "How do you test and mock MCP tool servers in continuous integration test suites?",
        4: "What are the latency considerations when chaining multiple MCP tool calls in a single conversational turn?",
        5: "Architect a secure enterprise MCP gateway with role-based access control, audit logging, and automated health checks."
    },
    25: {
        "title": "Evaluation Frameworks",
        1: "What are the core metrics used to evaluate RAG systems in frameworks like Ragas or TruLens (e.g. faithfulness, answer relevancy, context recall)?",
        2: "What is LLM-as-a-judge, and how do you calibrate judge models to avoid position bias and verbosity bias?",
        3: "How do you construct high-quality golden test datasets (ground truth Q&A pairs) for automated evaluation?",
        4: "How do you set statistical threshold gates in CI/CD pipelines to prevent deploying degraded prompts or models?",
        5: "Design an automated continuous evaluation system that monitors live production queries and flags quality regressions."
    },
    26: {
        "title": "Red Teaming & Adversarial Testing",
        1: "What are the most common vulnerability vectors in LLM applications, such as indirect prompt injection and data exfiltration?",
        2: "How do you conduct automated red-teaming simulations to probe an agent's guardrails before public release?",
        3: "How does indirect prompt injection exploit third-party untrusted web pages or documents retrieved during RAG?",
        4: "What techniques do you use to detect and quarantine adversarial inputs in real-time without increasing end-user latency?",
        5: "Architect a defensive multi-layered security architecture with input validation, output sanitization, and execution sandboxing."
    },
    27: {
        "title": "Security, Privacy & Guardrails",
        1: "How do guardrail frameworks like NeMo Guardrails or Llama Guard enforce topical boundaries and safety policies?",
        2: "How do you detect and mask Personally Identifiable Information (PII) before logging prompts or storing chat transcripts?",
        3: "How do you enforce deterministic output formatting and block toxic or compliance-violating responses?",
        4: "How do you balance guardrail model latency with end-user response times in streaming architectures?",
        5: "Design an enterprise AI security policy engine enforcing strict data boundaries, audit trails, and zero data retention guarantees."
    },
    28: {
        "title": "Docker & Kubernetes Deployment",
        1: "How do you write an optimized Dockerfile for a Python AI service with multi-stage builds and minimal image size?",
        2: "How do you configure GPU device passthrough (NVIDIA Container Toolkit) in Docker and Kubernetes environments?",
        3: "How do you configure Horizontal Pod Autoscaling (HPA) in Kubernetes based on custom metrics like GPU utilization or queue depth?",
        4: "How do you structure Kubernetes liveness and readiness probes for services that load heavy model weights into memory on startup?",
        5: "Design a high-availability Kubernetes deployment architecture for a distributed LLM inference cluster with rolling zero-downtime updates."
    },
    29: {
        "title": "Monitoring, Logging & Observability",
        1: "What are the key telemetry signals to monitor for production LLMs (e.g. time-to-first-token, token count, cost, error rates)?",
        2: "How do you implement distributed tracing with OpenTelemetry to track a request from frontend through vector DB to LLM API?",
        3: "How do you detect semantic drift and hallucination rate spikes in live production traffic?",
        4: "How do you structure structured JSON application logs to allow rapid debugging and cost attribution across user accounts?",
        5: "Design an end-to-end observability dashboard alerting on latency anomalies, cost spikes, and quality degradation."
    },
    30: {
        "title": "CI/CD & Automated Testing",
        1: "How do you structure automated GitHub Actions workflows for Python backend testing, linting, and type checking?",
        2: "How do you run comprehensive unit and integration test suites without making expensive or flaky external API calls?",
        3: "How do you incorporate prompt regression testing and model benchmark evaluations into pull request CI checks?",
        4: "How do you implement blue-green or canary deployments when releasing updated AI model versions to production?",
        5: "Design an enterprise CI/CD pipeline with automated testing, security scanning, evaluation benchmarking, and automated rollback."
    },
    31: {
        "title": "Capstone Project & Final Demo",
        1: "Can you walk through the end-to-end system architecture of your AI capstone project and the core engineering trade-offs you made?",
        2: "What was the most challenging technical roadblock you encountered during your capstone build, and how did you resolve it?",
        3: "If you had to scale your capstone application to handle 100x the current query volume, what architectural bottlenecks would you address first?",
        4: "How did you measure and validate the accuracy and latency metrics of your final capstone application?",
        5: "Defend your choice of tech stack (vector store, LLM provider, framework) against viable alternatives for your capstone problem domain."
    }
}


def _get_curriculum_question(day_num: int, level: int = 3, question_index: int = 0) -> str:
    """Retrieve an appropriate question for a given day and difficulty level."""
    day_data = CURRICULUM_QUESTIONS.get(day_num, CURRICULUM_QUESTIONS[7])
    lvl = max(1, min(5, level))
    return day_data.get(lvl, day_data.get(3, f"Can you explain the key concepts and practical applications of Day {day_num}?"))


def _mock_llm_response(system_prompt: str, user_prompt: str) -> str:
    """
    Intelligent mock responder for offline execution, automated testing,
    and fast demoing when no API keys are available.
    """
    lower = user_prompt.lower()

    # 1. Final feedback prompt
    if "write the final interview feedback" in lower or "final feedback" in lower or '"summary":' in lower:
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

    # 2. Answer evaluation prompt
    if "you are evaluating a candidate's answer" in lower or "the question that was asked:" in lower or "technical_correctness" in lower:
        # Check for non-answers, unrelated chatter, food, or extreme brevity
        non_technical_words = ["samosa", "food", "pizza", "burger", "hello", "hi", "test", "blah", "idk", "don't know", "not sure"]
        is_irrelevant = any(w in lower for w in non_technical_words) and len(lower) < 80
        is_too_short = len(lower.strip()) < 15

        if is_irrelevant or is_too_short:
            return json.dumps({
                "score": 2,
                "understanding": "none",
                "technical_correctness": "incorrect",
                "strengths": ["Response received"],
                "missing_concepts": ["Core technical mechanism", "Relevant architectural concepts"],
                "follow_up_needed": True,
                "recommended_action": "CLARIFY",
            })

        # Check for moderate vs strong technical responses
        if len(lower) < 60 or "maybe" in lower or "basic" in lower:
            return json.dumps({
                "score": 6,
                "understanding": "moderate",
                "technical_correctness": "partially_correct",
                "strengths": ["Understands the high-level concept"],
                "missing_concepts": ["Production edge cases and trade-offs"],
                "follow_up_needed": True,
                "recommended_action": "FOLLOW_UP",
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

    # 3. Follow-up question prompt
    if "follow-up question" in lower or "their answer was missing or unclear on" in lower:
        day_match = re.search(r'"day":\s*(\d+)', user_prompt)
        if not day_match:
            day_match = re.search(r"curriculum context for this topic:\s*day\s*(\d+)", lower)

        day_num = int(day_match.group(1)) if day_match else 7
        day_info = CURRICULUM_QUESTIONS.get(day_num, CURRICULUM_QUESTIONS[7])
        
        # Clarification vs deep dive
        if "none" in lower or "incorrect" in lower or "clarify" in lower:
            q = f"Let's refocus on {day_info['title']}. Could you describe the fundamental setup and basic workflow you used in that day's mission?"
        else:
            q = f"Could you elaborate further on {day_info['title']}—specifically, what practical engineering trade-offs and edge cases did you encounter?"
        
        return json.dumps({
            "question": q,
            "day": day_num,
            "level": 2,
            "topic": day_info["title"],
            "is_followup": True,
        })

    # 4. Question generation prompt
    if "write the next interview question" in lower or "curriculum day to base this question on" in lower:
        day_match = re.search(r'"day":\s*(\d+)', user_prompt)
        if not day_match:
            day_match = re.search(r"curriculum day to base this question on:\s*day\s*(\d+)", lower)
        
        day_num = int(day_match.group(1)) if day_match else 7
        
        level_match = re.search(r'"level":\s*(\d+)', user_prompt)
        if not level_match:
            level_match = re.search(r"target difficulty level.*?(\d+)", lower)
        level_num = int(level_match.group(1)) if level_match else 3
        
        day_data = CURRICULUM_QUESTIONS.get(day_num, CURRICULUM_QUESTIONS[7])
        q_text = _get_curriculum_question(day_num, level_num)
        
        return json.dumps({
            "question": q_text,
            "day": day_num,
            "level": level_num,
            "topic": day_data["title"],
        })

    return json.dumps({"reply": "Thank you. Let's continue to the next technical topic."})


def generate_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """
    Unified text generation entrypoint across Gemini, Anthropic, OpenAI, or Mock.
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Auto-select provider if not explicitly defined
    if not provider:
        if gemini_key:
            provider = "gemini"
        elif anthropic_key:
            provider = "anthropic"
        elif openai_key:
            provider = "openai"
        else:
            provider = "mock"

    # 1. Google Gemini
    if provider == "gemini" and gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            target_model = model or os.getenv("LLM_MODEL", "gemini-2.0-flash")
            response = client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config={"system_instruction": system_prompt}
            )
            return response.text
        except Exception as e:
            logger.warning("Gemini generation failed (%s), checking fallback...", e)
            if os.getenv("MOCK_FALLBACK_ON_ERROR", "true").lower() != "true":
                raise LLMServiceError(f"Gemini API error: {e}") from e

    # 2. Anthropic Claude
    if provider == "anthropic" and anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            target_model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
            response = client.messages.create(
                model=target_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.warning("Anthropic generation failed (%s), checking fallback...", e)
            if os.getenv("MOCK_FALLBACK_ON_ERROR", "true").lower() != "true":
                raise LLMServiceError(f"Anthropic API error: {e}") from e

    # 3. OpenAI
    if provider == "openai" and openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key, base_url=os.getenv("OPENAI_BASE_URL"))
            target_model = model or os.getenv("LLM_MODEL", "gpt-4o")
            response = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("OpenAI generation failed (%s), checking fallback...", e)
            if os.getenv("MOCK_FALLBACK_ON_ERROR", "true").lower() != "true":
                raise LLMServiceError(f"OpenAI API error: {e}") from e

    # 4. Fallback / Mock
    return _mock_llm_response(system_prompt, user_prompt)


class LLMServiceError(RuntimeError):
    """Raised when an LLM provider fails."""


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON text, stripping any markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMServiceError(f"LLM did not return valid JSON: {exc}\nRaw: {text[:200]}") from exc


def generate_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Generate structured JSON response from the LLM."""
    text = generate_text(system_prompt, user_prompt, model=model, max_tokens=max_tokens)
    return _parse_json_response(text)
