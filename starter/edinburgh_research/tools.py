"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolError, ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"
_VENUE_FILE = _SAMPLE_DATA / "venues.json"
_WEATHER_FILE = _SAMPLE_DATA / "weather.json"
_CATERING_FILE = _SAMPLE_DATA / "catering.json"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    search_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "venue_search")
    if search_count >= 3:
        return ToolResult(
            success=False,
            output={"error": "too_many_searches", "count": search_count},
            summary="STOP calling venue_search; use the results you already have.",
        )

    if not _VENUE_FILE.exists():
        raise ToolError(code="SA_TOOL_DEPENDENCY_MISSING", message="venue does not exist")

    with _VENUE_FILE.open("r", encoding="utf-8") as f:
        results = []
        venues = json.load(f)
        for venue in venues:
            if (
                venue["open_now"]
                and near.lower() in venue["area"].lower()
                and venue["seats_available_evening"] >= party_size
                and venue["hire_fee_gbp"] + venue["min_spend_gbp"] <= budget_max_gbp
            ):
                results.append(venue)
    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }

    summary = f"venue_search({near}, party={party_size}): {len(results)} result(s)"

    arguments = {
        "near": near,
        "party_size": party_size,
        "budget_max_gbp": budget_max_gbp,
    }

    record_tool_call(
        tool_name="venue_search",
        arguments=arguments,
        output=output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    if not _WEATHER_FILE.exists():
        raise ToolError(code="SA_TOOL_DEPENDENCY_MISSING", message="weather data does not exist")
    with _WEATHER_FILE.open("r", encoding="utf-8") as f:
        weather_data = json.load(f)
        city_key = city.lower()
        if city_key not in weather_data:
            error = ToolError(
                code="SA_TOOL_INVALID_INPUT",
                message=f"city '{city}' not found in weather data",
            )
            return ToolResult(success=False, output={}, summary="", error=error)
        city_weather = weather_data[city_key]
        if date not in city_weather:
            error = ToolError(
                code="SA_TOOL_INVALID_INPUT",
                message=f"weather data for city '{city}' does not exist for date '{date}'",
            )
            return ToolResult(success=False, output={}, summary="", error=error)
        entry = city_weather[date]
        output = {
            "city": city,
            "date": date,
            "condition": entry["condition"],
            "temperature_c": entry["temperature_c"],
            "precip_mm": entry["precip_mm"],
            "wind_kph": entry["wind_kph"],
        }
        summary = f"get_weather({city}, {date}): {entry['condition']}, {entry['temperature_c']}C"
        record_tool_call(
            tool_name="get_weather",
            arguments={"city": city, "date": date},
            output=output,
        )
        return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    if not _VENUE_FILE.exists() or not _CATERING_FILE.exists():
        raise ToolError(
            code="SA_TOOL_DEPENDENCY_MISSING", message="venue or catering data does not exist"
        )

    with _VENUE_FILE.open("r", encoding="utf-8") as f:
        venues = json.load(f)
        venues_by_id = {venue["id"]: venue for venue in venues}
        if venue_id not in venues_by_id:
            error = ToolError(code="SA_TOOL_INVALID_INPUT", message="venue does not exist")
            return ToolResult(success=False, output={}, summary="", error=error)

        selected_venue = venues_by_id[venue_id]

    with _CATERING_FILE.open("r", encoding="utf-8") as f:
        catering = json.load(f)
        base_rates = catering["base_rates_gbp_per_head"]
        venue_modifiers = catering["venue_modifiers"]
        if catering_tier not in base_rates:
            error = ToolError(
                code="SA_TOOL_INVALID_INPUT", message=f"{catering_tier} does not exist"
            )
            return ToolResult(success=False, output={}, summary="", error=error)
        if venue_id not in venue_modifiers:
            error = ToolError(code="SA_TOOL_INVALID_INPUT", message=f"{venue_id} does not exist")
            return ToolResult(success=False, output={}, summary="", error=error)

        base_per_head = base_rates[catering_tier]
        venue_mult = venue_modifiers[venue_id]
        subtotal_gbp = base_per_head * venue_mult * party_size * max(1, duration_hours)
        service_gbp = subtotal_gbp * catering["service_charge_percent"] / 100
        total_gbp = (
            subtotal_gbp
            + service_gbp
            + selected_venue["hire_fee_gbp"]
            + selected_venue["min_spend_gbp"]
        )
        deposit_required_gbp = 0

        if total_gbp < 300:
            deposit_required_gbp = 0
        elif total_gbp <= 1000:
            deposit_required_gbp = int(total_gbp * 0.20)
        else:
            deposit_required_gbp = int(total_gbp * 0.30)

    total_gbp_int = int(total_gbp)
    deposit_required_gbp_int = int(deposit_required_gbp)

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": int(subtotal_gbp),
        "service_gbp": int(service_gbp),
        "total_gbp": total_gbp_int,
        "deposit_required_gbp": deposit_required_gbp_int,
    }

    arguments = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }
    record_tool_call(tool_name="calculate_cost", arguments=arguments, output=output)
    summary = f"calculate_cost({venue_id}, {party_size}): total £{total_gbp_int}, deposit £{deposit_required_gbp_int}"

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    html_path = session.workspace_dir / "flyer.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html = f"""<!DOCTYPE html>
    <html>
    <head><title>Booking — {event_details["venue_name"]}</title></head>
    <body>
    <p>Event Details</p>
    <h1 data-testid="venue_name">{event_details["venue_name"]}</h1>
    <p data-testid="date">{event_details["date"]}</p>
    <p data-testid="time">{event_details["time"]}</p>
    <p data-testid="party_size">{event_details["party_size"]}</p>
    <p data-testid="condition">{event_details["condition"]}</p>
    <p data-testid="temperature_c">{event_details["temperature_c"]}C</p>
    <p data-testid="total_gbp">£{event_details["total_gbp"]}</p>
    <p data-testid="deposit_required_gbp">£{event_details["deposit_required_gbp"]}</p>
    </body>
    </html>
    """
    bytes_written = html_path.write_text(html, encoding="utf-8")
    output = {
        "path": "workspace/flyer.html",
        "bytes_written": bytes_written,
    }
    summary = f"generate_flyer: wrote workspace/flyer.html ({bytes_written} chars)"
    record_tool_call(tool_name="generate_flyer", arguments=event_details, output=output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
