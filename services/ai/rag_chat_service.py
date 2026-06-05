"""
RAG Chat Service — Incident-Scoped QA with Dual-Layer Guardrails

Architecture:
  1. Fetch incident context from MySQL
  2. Guardrail Layer 1: Mistral system prompt locks the LLM to the incident title
  3. ChromaDB retrieval filtered by incident_id (scoped RAG)
  4. Fallback: use DB data if ChromaDB has no indexed chunks for this incident
  5. Mistral streaming response with SSE yielding
  6. Guardrail Layer 2: intercept [GUARDRAIL] tag in response stream
"""

import os
import json
import logging
from typing import Generator

from mistralai.client import MistralClient

from database.db_connection import get_db_connection
from services.ai.chroma_service import ChromaService

logger = logging.getLogger(__name__)

API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL   = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

_mistral = MistralClient(api_key=API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_incident(incident_id: int) -> dict | None:
    """Fetch full incident row (+ AI analysis) from MySQL."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            i.id, i.title, i.description, i.priority,
            i.status, i.source, i.ticket_id, i.assignee,
            ai.summary, ai.solution, ai.risk_score AS ai_risk_score,
            ai.estimated_resolution_time
        FROM incidents i
        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (SELECT MAX(id) FROM incident_ai_analysis WHERE incident_id = i.id)
        WHERE i.id = %s
    """, (incident_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def _build_context_block(incident: dict, chroma_docs: list[str]) -> str:
    """
    Build the context block injected into the LLM system prompt.
    Uses ChromaDB docs if available, otherwise falls back to the incident DB fields.
    """
    if chroma_docs:
        context_body = "\n\n---\n".join(chroma_docs)
        source_note  = "Retrieved from vector knowledge base (ChromaDB)."
    else:
        # Graceful fallback — build context from MySQL fields directly
        context_body = f"""Title: {incident.get('title', 'N/A')}

Description:
{incident.get('description') or 'Not provided.'}

Priority: {incident.get('priority', 'N/A')}
Status: {incident.get('status', 'N/A')}
Source: {incident.get('source', 'N/A')}
Ticket ID: {incident.get('ticket_id', 'N/A')}
Assignee: {incident.get('assignee') or 'Unassigned'}

AI Summary:
{incident.get('summary') or 'Not yet analyzed.'}

AI Solution:
{incident.get('solution') or 'Not yet analyzed.'}

Estimated Resolution Time: {incident.get('estimated_resolution_time') or 'Unknown'}
AI Risk Score: {incident.get('ai_risk_score') or 'N/A'}"""
        source_note = "Sourced directly from incident database (no vector index found for this incident)."

    return f"{context_body}\n\n[{source_note}]"


def _build_system_prompt(incident: dict, context_block: str) -> str:
    """
    Build the hard-constrained system prompt.
    Layer 1 guardrail: LLM is explicitly forbidden from answering off-topic questions.
    """
    title     = incident.get("title", "Unknown Incident")
    ticket_id = incident.get("ticket_id", "N/A")
    priority  = incident.get("priority", "N/A")
    status    = incident.get("status", "N/A")

    return f"""You are an expert ITSM Incident Assistant locked exclusively to the following incident:

INCIDENT SCOPE LOCK
Title    : {title}
Ticket ID: {ticket_id}
Priority : {priority}
Status   : {status}

INCIDENT CONTEXT DATA
{context_block}

STRICT BEHAVIORAL RULES — READ CAREFULLY

1. You MAY ONLY answer questions that are directly related to the incident described above:
   "{title}"

2. If the user asks about ANYTHING unrelated to this specific incident — including:
   - Other incidents or tickets
   - General knowledge, trivia, weather, jokes, coding questions
   - Personal advice or anything outside this incident's scope
   → You MUST respond with ONLY the following exact text (nothing else):
     [GUARDRAIL] I can only assist with questions about: "{title}"

3. **Assume user questions are about the current incident**, even if phrased generally. If a question *could* relate to the incident, answer it within that context.
4. Be concise, technical, and actionable.
5. Reference the incident context data above when answering.
6. Do NOT hallucinate — if the context does not contain enough information, say so clearly.
7. Do NOT answer general IT questions unless they are directly applicable to THIS incident.

You are now ready to answer questions about this specific incident.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

GUARDRAIL_TAG = "[GUARDRAIL]"


def stream_chat_response(incident_id: int, user_message: str) -> Generator[str, None, None]:
    """
    Full RAG chat pipeline with SSE streaming.

    Yields SSE-formatted strings:
      data: {"type": "token", "content": "..."}
      data: {"type": "guardrail", "content": "..."}
      data: {"type": "error", "content": "..."}
      data: {"type": "done"}
    """

    # ── 1. Fetch incident ────────────────────────────────────────────────────
    incident = _fetch_incident(incident_id)
    if not incident:
        yield f'data: {json.dumps({"type": "error", "content": "Incident not found."})}\n\n'
        yield f'data: {json.dumps({"type": "done"})}\n\n'
        return

    title = incident.get("title", "Unknown Incident")

    # ── 2. ChromaDB scoped retrieval ─────────────────────────────────────────
    chroma_id = f"{incident.get('source')}-{incident.get('ticket_id')}"
    chroma_docs = ChromaService.search_by_incident_id(
        incident_id=chroma_id,
        query_text=user_message,
        top_k=5
    )
    logger.info(
        f"[RAG Chat] incident_id={incident_id} chroma_id={chroma_id} "
        f"docs_found={len(chroma_docs)}"
    )

    # ── 3. Build context + system prompt ────────────────────────────────────
    context_block = _build_context_block(incident, chroma_docs)
    system_prompt = _build_system_prompt(incident, context_block)

    # ── 4. Mistral streaming call (v1 SDK) ───────────────────────────────────
    try:
        accumulated = ""

        stream = _mistral.chat_stream(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        )

        for event in stream:
            # v1 SDK: event is ChatCompletionStreamResponse, delta is on choices[0].delta.content
            delta = ""
            try:
                delta = event.choices[0].delta.content or ""
            except (AttributeError, IndexError, TypeError):
                continue

            accumulated += delta

            # ── Layer 2 Guardrail: intercept [GUARDRAIL] tag ─────────
            if GUARDRAIL_TAG in accumulated:
                friendly_msg = (
                    f'I can only assist with questions directly related to: '
                    f'**"{title}"**. '
                    f'Please ask something about this specific incident.'
                )
                yield f'data: {json.dumps({"type": "guardrail", "content": friendly_msg})}\n\n'
                yield f'data: {json.dumps({"type": "done"})}\n\n'
                return

            if delta:
                yield f'data: {json.dumps({"type": "token", "content": delta})}\n\n'

        yield f'data: {json.dumps({"type": "done"})}\n\n'

    except Exception as e:
        logger.error(f"[RAG Chat] Mistral streaming error: {e}")
        yield (
            f'data: {json.dumps({"type": "error", "content": "AI service temporarily unavailable. Please try again."})}\n\n'
        )
        yield f'data: {json.dumps({"type": "done"})}\n\n'
