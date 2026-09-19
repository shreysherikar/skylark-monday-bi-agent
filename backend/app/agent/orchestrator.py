"""Groq tool-use conversational agent orchestrator for Skylark Drones BI.

Uses the official Python Groq SDK to orchestrate conversational business intelligence
reasoning with configurable open-weights models (default: llama-3.3-70b-versatile).

All data calculations route strictly through deterministic analytics functions in
`tools.py`, which query Monday.com read-only MCP tools. The LLM handles query
interpretation, tool selection, clarification, and executive explanation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from groq import BadRequestError, Groq

from app.agent.clarification import check_query_ambiguity
from app.agent.tools import execute_tool, get_groq_tools
from app.config import settings

logger = logging.getLogger(__name__)


class AgentLLMError(RuntimeError):
    """Raised when the upstream LLM service fails or repeatedly returns invalid tool calls.

    Callers (e.g. the FastAPI layer) should translate this into a controlled
    service-unavailable response rather than leaking a raw provider stack trace.
    """

SYSTEM_PROMPT = """You are the Senior Business Intelligence Agent for Skylark Drones, analyzing commercial Work Orders and Deal Funnel data from Monday.com.

CORE PRINCIPLES & OPERATIONAL RULES:
1. NEVER CALCULATE OR ESTIMATE NUMBERS IN YOUR HEAD. Every metric, sum, percentage, count, and currency figure in your response MUST be obtained directly from your analytics tool calls.
2. MANDATORY DATA-QUALITY CAVEAT INJECTION:
   - Both boards contain genuinely messy data. Deals fields such as Closure Probability, Masked Deal value and Close Date (A) have severe null rates, and Work Orders contain legitimate negative amounts (credit-balance receivables, negative billing adjustments) plus bookkeeping flags (billed value recorded without an invoice status).
   - NEVER quote data-quality statistics from memory or from these instructions. Only ever state the exact counts, percentages and amounts returned by your tool calls, because those reflect the live board state at query time.
   - Blank values are NOT zero (e.g. unbilled orders, uncollected amounts).
   - Whenever reporting metrics, you must explicitly integrate and prominently highlight the caveats returned by the tools.
3. CROSS-BOARD INTELLIGENCE & FOUNDER-LEVEL QUESTIONS:
   - Use `get_cross_board_delivery` to answer strategic questions connecting CRM Deals to Operations/Fulfillment Work Orders.
   - Always state the actual live link coverage percentage and count reported by the tool (e.g., 15 of 176 work orders linked via native Monday Connect Boards).
   - Commercial Risk Audit: When evaluating operational risks or unclosed deals, quote the exact count, total value, and specific high-risk work orders (e.g. operations Ongoing/Completed on Open/Hold deals) from `commercial_risk`.
   - Value Realization & Variance: When evaluating contract value vs booked/billed revenue, cite the exact contract leakage and scope expansion totals from `value_variance`.
   - Execution Backlog: When evaluating sales-to-delivery handoff, quote the count and pipeline value of Won deals with no Work Orders recorded from `won_deals_backlog`.
   - Unlinked Exposure: Never present linked metrics in isolation without highlighting the unlinked work orders exposure from `unlinked_exposure`.
4. TONE & FORMAT:
   - Executive, sharp, objective, and transparent about data limitations.
   - Use structured markdown with clear bullet points, bold KPIs, and tables where appropriate.
5. CURRENCY FORMATTING (STRICT REQUIREMENT):
   - ALL monetary amounts across Skylark Drones are strictly in Indian Rupees (₹ / INR).
   - NEVER use the dollar sign ($) or USD when presenting revenue, deal values, receivables, or pipeline totals.
   - ALWAYS format monetary numbers with the Rupee symbol '₹' (e.g. ₹X,XX,XXX or ₹XX.XM).
"""


def sanitize_currency_symbols(text: str) -> str:
    """Enforces Indian Rupee (₹) formatting and prevents accidental dollar ($) mislabeling.

    Replaces any instances of '$' followed by digits (e.g. '$28,138,196.33' -> '₹28,138,196.33')
    or '$' followed by whitespace and digits, as well as explicit 'USD' currency markers.
    """
    if not text:
        return text
    import re
    cleaned = re.sub(r"\$\s*(\d)", r"₹\1", text)
    cleaned = re.sub(r"\bUSD\b", "INR", cleaned)
    return cleaned



@dataclass
class AgentResponse:
    """Standardized response object from the BI Agent."""
    response: str
    tools_used: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    suggested_options: list[str] = field(default_factory=list)


class AgentOrchestrator:
    """Orchestrates Groq conversational reasoning and deterministic tool execution."""

    def __init__(
        self,
        client: Groq | None = None,
        model: str | None = None,
    ) -> None:
        self.model = model or settings.groq_model
        self._client = client

    @property
    def client(self) -> Groq:
        """Lazily initialize the Groq client."""
        if self._client is None:
            if not settings.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY is not configured in environment or settings. "
                    "Cannot initialize Groq agent client."
                )
            self._client = Groq(api_key=settings.groq_api_key)
        return self._client

    def _create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_attempts: int = 2,
    ) -> Any:
        """Invokes the Groq chat completion endpoint with resilience.

        The model occasionally emits structurally invalid tool calls (for example
        passing `null` for an optional string argument). Groq rejects those with an
        HTTP 400 `tool_use_failed` error. We retry once, then surface a controlled
        AgentLLMError so the API layer can respond with 503 instead of a raw 500.

        Raises:
            AgentLLMError: When the provider is unreachable, misconfigured, or keeps
                returning invalid tool calls.
        """
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self.client.chat.completions.create(  # type: ignore[call-overload]
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2048,
                )
            except BadRequestError as ex:
                last_error = ex
                detail = str(ex).lower()
                is_tool_validation_error = "tool" in detail and (
                    "validation" in detail or "tool_use_failed" in detail
                )
                if is_tool_validation_error and attempt < max_attempts - 1:
                    logger.warning(
                        "Groq rejected a tool call (attempt %d/%d); retrying: %s",
                        attempt + 1,
                        max_attempts,
                        str(ex)[:200],
                    )
                    continue
                logger.error("Groq rejected the request: %s", str(ex)[:300])
                raise AgentLLMError(
                    "The language model service could not process this request "
                    "(invalid tool call). Please try rephrasing the question."
                ) from ex
            except Exception as ex:
                logger.exception("Groq chat completion failed")
                raise AgentLLMError(
                    "The language model service is currently unavailable. Please try again shortly."
                ) from ex

        raise AgentLLMError(
            "The language model service repeatedly produced an invalid response. Please try again."
        ) from last_error

    def ask(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        max_tool_iterations: int = 5,
    ) -> AgentResponse:
        """Processes a natural language query through ambiguity check and the Groq tool loop.

        Args:
            query: User's input question or instruction.
            history: Optional prior conversation turns: [{'role': 'user'|'assistant', 'content': '...'}]
            max_tool_iterations: Safeguard against runaway tool invocation loops.
        """
        logger.info("Processing user query with Groq (%s): '%s'", self.model, query)

        # 1. Deterministic Ambiguity & Clarification Decision Tree (§8)
        clarification_check = check_query_ambiguity(query)
        if clarification_check.needs_clarification:
            logger.info("Query triggered clarification: %s", clarification_check.ambiguity_type)
            return AgentResponse(
                response=clarification_check.clarification_message or "Could you clarify your request?",
                tools_used=[],
                caveats=[],
                needs_clarification=True,
                suggested_options=clarification_check.suggested_options,
            )

        # 2. Build conversation message chain
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        if history:
            for turn in history:
                messages.append({
                    "role": turn.get("role", "user"),
                    "content": turn.get("content", ""),
                })

        messages.append({
            "role": "user",
            "content": query,
        })

        tools_invoked: list[str] = []
        collected_caveats: list[str] = []
        groq_tools = get_groq_tools()

        # 3. Tool Calling Loop with Groq
        for iteration in range(max_tool_iterations):
            chat_completion = self._create_completion(messages, groq_tools)

            msg = chat_completion.choices[0].message
            tool_calls = msg.tool_calls

            # If no tool calls were made, we have our final text response
            if not tool_calls:
                final_text = sanitize_currency_symbols(msg.content or "")
                return AgentResponse(
                    response=final_text.strip(),
                    tools_used=tools_invoked,
                    caveats=collected_caveats,
                    needs_clarification=False,
                )

            # Record assistant turn with tool calls
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_turn)

            # Execute tools and append tool results
            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args_raw = tc.function.arguments or "{}"
                tools_invoked.append(fn_name)

                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except (ValueError, TypeError, AttributeError):
                    fn_args = {}

                try:
                    tool_output = execute_tool(fn_name, fn_args)
                    if isinstance(tool_output, dict) and "caveats" in tool_output:
                        for c in tool_output["caveats"]:
                            if c not in collected_caveats:
                                collected_caveats.append(c)
                    content_str = json.dumps(tool_output, default=str)
                except Exception as ex:
                    logger.exception("Error executing tool '%s' via Groq dispatcher", fn_name)
                    content_str = json.dumps({"error": str(ex)})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": content_str,
                })

        logger.warning("Max tool iterations (%d) reached for Groq query.", max_tool_iterations)
        return AgentResponse(
            response="I was unable to complete the multi-step analysis within the maximum tool depth. Please narrow your query.",
            tools_used=tools_invoked,
            caveats=collected_caveats,
            needs_clarification=False,
        )

