"""Groq tool-use conversational agent orchestrator for Skylark Drones BI.

Uses the official Python Groq SDK to orchestrate conversational business intelligence
reasoning with configurable open-weights models (default: openai/gpt-oss-120b).

All data calculations route strictly through deterministic analytics functions in
`tools.py`, which query Monday.com read-only MCP tools. The LLM handles query
interpretation, tool selection, clarification, and executive explanation.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from groq import BadRequestError, Groq, RateLimitError

from app.agent.clarification import check_query_ambiguity
from app.agent.structured_response import generate_structured_response
from app.agent.tools import execute_tool, get_groq_tools
from app.config import settings
from app.monday_mcp.client import MondayAPIError

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
   - NEVER quote data-quality statistics from memory or from these instructions. Only ever state the exact counts, percentages, and amounts dynamically returned by your tool calls, because those reflect the live board state at query time.
   - Blank values are NOT zero. When explaining null billed or collected values, quote the exact null counts from the tool caveats (orders with null billed values and orders with null collected amounts are unrecorded values rather than zero, not confirmed outstanding balances).
   - Whenever reporting metrics, you must explicitly integrate and prominently highlight the caveats returned by the tools.
   - Data quality labels: When reporting completely empty columns, report the 4 100% null columns (Expected Billing Month, Actual Collection Month, Collection status, Collection Date) as returned by the tool. Report null percentages accurately as provided by the data quality tool.
3. RECEIVABLES & BILLINGS PRECISION:
   - Do NOT say "as of today" (e.g. do not say "Total Outstanding Receivables (as of today)"), because calculations are across current Work Orders rather than a historical date-cutoff ledger.
   - Use: "Current Outstanding Receivables" or "Outstanding Receivables Across Current Work Orders", followed by Net and Gross receivables dynamically provided by the tool.
   - For Work Orders time-sliced by period, explicitly label values as "Bookings (by PO date)". Explicitly note that billed and collected values cannot be time-sliced by quarter because collection/billing dates are 100% null.
   - If asked for Days Sales Outstanding (DSO) or invoice aging, explicitly refuse and explain that collection dates and billing months are 100% null in Monday.com.
4. CROSS-BOARD INTELLIGENCE & FOUNDER-LEVEL QUESTIONS:
   - Use `get_cross_board_delivery` to answer strategic questions connecting CRM Deals to Operations/Fulfillment Work Orders.
   - Always state the actual live link coverage percentage and count dynamically reported by the tool.
   - Commercial Risk: Distinguish "unclosed" from "unwon" and cite the exact order counts and financial value at risk on non-won deals (Open, On Hold, or Dead deals where orders are executing or completed).
   - Value Realization & Variance: Cite contract leakage and scope expansion totals dynamically returned in `value_variance`.
   - Execution Backlog: Cite the count and pipeline value of Won deals with no Work Orders dynamically returned in `won_deals_backlog`.
   - Unlinked Exposure: State the exact unlinked booked work-order value and order count from `unlinked_exposure`: "Booked work-order value currently unlinked to a confirmed CRM deal on Monday.com. Deal attribution cannot be established from confirmed native links." NEVER call it "unknown contract status" or imply contracts are unknown.
5. TEMPORAL & SECTOR AWARENESS:
   - When users ask about a specific timeframe (e.g. "this quarter", "last quarter", "Q4 FY25-26"), pass the period string into tool calls.
   - If a requested period yields 0 deals/orders because the historical records end in early 2026, state plainly that no activity is recorded in that window and present the nearest historical quarters with data alongside all-time benchmarks.
   - For sector "Energy", note that metrics aggregate Renewables + Powerline, and present individual component breakdowns when available.
6. WIN RATE & COMMERCIAL LEADERS:
   - When discussing deal conversions, report Win Rate as Won / (Won + Dead), citing sample sizes and noting that Open and On Hold deals are excluded from the denominator.
   - Owner rankings must NEVER conflate Deals CRM owners with Work Orders BD/KAM personnel. Always report them as distinct functional rankings:
     * "Deals Sales Owner (CRM)" - originates and closes deals (ranked by Won Deal Value and Win Rate).
     * "Work Orders BD/KAM Personnel (Operations)" - manages project bookings and execution (ranked by Booked Value by PO date).
     Do NOT claim a single "top BD manager" across both boards because masked codes between Deals and Work Orders represent separate functional roles and unconfirmed cross-board identity.
7. TONE & GROUNDED RECOMMENDATIONS:
   - Executive, sharp, objective, and transparent about data limitations.
   - Use structured markdown with clear bullet points, bold KPIs, and tables where appropriate.
   - Do NOT invent arbitrary quantitative targets or policy mandates (e.g., do not say "Aim for ≥50% coverage within 30 days" or "Implement a Deal-Won gate").
   - Frame suggestions strictly as potential review items:
     * "Potential action: Review and increase native Deal ↔ Work Order linkage coverage."
     * "Potential action: Review whether Close Date, Closure Probability, and Deal Value should be mandatory fields."
8. CURRENCY FORMATTING (STRICT REQUIREMENT):
   - ALL monetary amounts across Skylark Drones are strictly in Indian Rupees (₹ / INR).
   - NEVER use the dollar sign ($) or USD when presenting revenue, deal values, receivables, or pipeline totals.
   - ALWAYS format monetary numbers with the Rupee symbol '₹' (e.g. ₹X,XX,XXX or ₹XX.XM).
9. API UNAVAILABILITY & ERROR TRANSPARENCY:
   - If a tool indicates that Monday.com data is temporarily unavailable, state clearly and transparently: "Monday.com data is temporarily unavailable. No fabricated or stale business values were used." Never guess, hallucinate, or fabricate metrics when the upstream data source is unreachable.
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


def _compact_tool_output_for_llm(fn_name: str, tool_output: Any) -> Any:
    """Compacts tool output payloads so they fit comfortably within upstream LLM context limits (e.g. Groq 8000 TPM limit).
    
    Preserves 100% of KPIs, summary totals, percentages, breakdowns, and caveats, while truncating
    excessively large raw item record lists to concise sample previews.
    """
    if not isinstance(tool_output, dict):
        return tool_output

    out = dict(tool_output)

    if fn_name == "get_leadership_update":
        rev = out.get("revenue_kpis") or {}
        pipe = out.get("pipeline_kpis") or {}
        deliv = out.get("delivery_kpis") or {}
        return {
            "period": out.get("period"),
            "markdown_briefing": out.get("markdown_briefing"),
            "summary_kpis": {
                "active_pipeline_unweighted_value": pipe.get("active_pipeline_unweighted_value"),
                "active_pipeline_weighted_value": pipe.get("active_pipeline_weighted_value"),
                "won_deals_total_value": pipe.get("won_deals_total_value"),
                "total_order_value_excl_gst": rev.get("total_order_value_excl_gst"),
                "total_billed_value_excl_gst": rev.get("total_billed_value_excl_gst"),
                "total_collected_value_incl_gst": rev.get("total_collected_value_incl_gst"),
                "net_receivables": rev.get("net_receivables"),
                "gross_positive_receivables": rev.get("gross_positive_receivables"),
                "credit_balance_total": rev.get("credit_balance_total"),
                "matched_orders_count": deliv.get("matched_orders_count"),
                "total_work_orders": deliv.get("total_work_orders"),
                "link_coverage_percentage": deliv.get("link_coverage_percentage"),
                "completed_and_won_count": deliv.get("completed_and_won_count"),
            },
            "caveats": pipe.get("caveats", []) + rev.get("caveats", []) + deliv.get("caveats", []),
        }

    elif fn_name == "get_cross_board_delivery":
        if "linked_items" in out and isinstance(out["linked_items"], list):
            items = out["linked_items"]
            out["total_linked_items"] = len(items)
            out["sample_linked_items"] = [
                {
                    "wo_serial": it.get("wo_serial"),
                    "deal_name": it.get("deal_name"),
                    "deal_status": it.get("deal_status"),
                    "wo_execution_status": it.get("wo_execution_status"),
                    "wo_amount_excl_gst": it.get("wo_amount_excl_gst"),
                    "is_commercial_risk": it.get("is_commercial_risk"),
                    "risk_reason": it.get("risk_reason"),
                }
                for it in items[:4]
            ]
            del out["linked_items"]

        if "matched_sample" in out:
            del out["matched_sample"]

        if "commercial_risk" in out and isinstance(out["commercial_risk"], dict):
            risk_dict = dict(out["commercial_risk"])
            if "risk_orders" in risk_dict and isinstance(risk_dict["risk_orders"], list):
                risk_dict["risk_orders_sample"] = risk_dict["risk_orders"][:4]
                risk_dict["total_risk_orders_count"] = len(risk_dict["risk_orders"])
                del risk_dict["risk_orders"]
            out["commercial_risk"] = risk_dict

        if "won_deals_backlog" in out and isinstance(out["won_deals_backlog"], dict):
            backlog_dict = dict(out["won_deals_backlog"])
            if "sample_won_deals_without_wo" in backlog_dict and isinstance(backlog_dict["sample_won_deals_without_wo"], list):
                backlog_dict["sample_won_deals_without_wo"] = backlog_dict["sample_won_deals_without_wo"][:4]
            out["won_deals_backlog"] = backlog_dict

    elif fn_name == "get_data_quality_report":
        if "gst_check" in out and isinstance(out["gst_check"], dict):
            gst = dict(out["gst_check"])
            if "discrepancies" in gst and isinstance(gst["discrepancies"], list):
                gst["sample_discrepancies"] = gst["discrepancies"][:4]
                gst["total_discrepancies"] = len(gst["discrepancies"])
                del gst["discrepancies"]
            out["gst_check"] = gst

    elif fn_name == "get_pipeline_summary":
        if "owner_breakdown" in out and isinstance(out["owner_breakdown"], list):
            out["owner_breakdown"] = out["owner_breakdown"][:5]
        if "nearest_quarters_data" in out and isinstance(out["nearest_quarters_data"], list):
            out["nearest_quarters_data"] = out["nearest_quarters_data"][:4]

    elif fn_name == "get_revenue_summary":
        if "owner_breakdown" in out and isinstance(out["owner_breakdown"], list):
            out["owner_breakdown"] = out["owner_breakdown"][:5]
        if "nearest_quarters_data" in out and isinstance(out["nearest_quarters_data"], list):
            out["nearest_quarters_data"] = out["nearest_quarters_data"][:4]

    return out


@dataclass
class AgentResponse:
    """Standardized response object from the BI Agent."""
    response: str
    tools_used: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    suggested_options: list[str] = field(default_factory=list)
    structured: dict[str, Any] | None = None


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
            except RateLimitError as rle:
                last_error = rle
                if attempt < max_attempts - 1:
                    sleep_s = 3.0 * (attempt + 1)
                    logger.warning(
                        "Groq rate limit hit (attempt %d/%d); sleeping %.1fs: %s",
                        attempt + 1,
                        max_attempts,
                        sleep_s,
                        str(rle)[:200],
                    )
                    time.sleep(sleep_s)
                    continue
                logger.error("Groq rate limit exceeded after %d attempts: %s", max_attempts, str(rle)[:300])
                raise AgentLLMError(
                    "The language model service is temporarily rate-limited. Please retry in a few moments."
                ) from rle
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
        last_structured: dict[str, Any] | None = None
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
                    structured=last_structured,
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

                    struct_obj = generate_structured_response(fn_name, tool_output)
                    if struct_obj is not None:
                        last_structured = struct_obj.model_dump()

                    compacted = _compact_tool_output_for_llm(fn_name, tool_output)
                    content_str = json.dumps(compacted, default=str)
                except MondayAPIError as mex:
                    logger.warning("Monday.com API error executing tool '%s': %s", fn_name, mex)
                    content_str = json.dumps({
                        "error": "Monday.com data is temporarily unavailable. No fabricated or stale business values were used.",
                        "details": str(mex),
                    })
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
            structured=last_structured,
        )

