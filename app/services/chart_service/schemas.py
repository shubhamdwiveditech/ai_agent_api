from pydantic import BaseModel, Field
from typing import Optional

# ── Schemas ───────────────────────────────────────────────────────────────────

class Dataset(BaseModel):
    label: Optional[str] = None
    data: list[float]


class ChartRequest(BaseModel):
    chart_type: str = Field(
        ...,
        description="One of: bar, horizontal_bar, line, area, pie, doughnut, scatter, radar, histogram",
        examples=["bar"],
    )
    labels: list[str] = Field(..., examples=[["Q1", "Q2", "Q3", "Q4"]])
    datasets: list[Dataset] = Field(
        ...,
        examples=[[{"label": "Revenue", "data": [100, 200, 300, 400]}]],
    )
    title: Optional[str] = None
    width: int = Field(10, ge=4, le=20)
    height: int = Field(6, ge=3, le=15)


class ChartResponse(BaseModel):
    base64: str
    data_url: str
    format: str = "png"


class ChatRequest(BaseModel):
    message: str = Field(..., examples=["Show me a bar chart of Q1-Q4 revenue: 100, 200, 300, 400"])
    conversation_history: Optional[list[dict]] = Field(
        default=None,
        description="Optional previous messages for multi-turn conversations.",
    )


class ChatResponse(BaseModel):
    response: str
    chart: Optional[ChartResponse] = None
    tool_calls: list[dict] = []
