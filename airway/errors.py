from __future__ import annotations

from fastmcp.exceptions import ToolError

from airway.config import AirwayError


def to_tool_error(err: AirwayError) -> ToolError:
    return ToolError(err.message)
