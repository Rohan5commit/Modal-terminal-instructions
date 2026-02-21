import os

import dash
import httpx
import pandas as pd
import plotly.express as px
from dash import Input, Output, dcc, html


API_BASE = os.getenv("BIAS_API_BASE_URL", "http://localhost:8000")

app = dash.Dash(__name__)
app.title = "LLM Bias Dashboard"

app.layout = html.Div(
    [
        html.H2("Behavioral Bias Benchmark Dashboard"),
        dcc.Input(id="run-id", type="text", placeholder="Optional run_id filter"),
        html.Button("Refresh", id="refresh-btn", n_clicks=0),
        dcc.Graph(id="bias-bar-chart"),
        html.Div(id="status"),
    ],
    style={"maxWidth": "1000px", "margin": "0 auto", "padding": "24px"},
)


@app.callback(
    Output("bias-bar-chart", "figure"),
    Output("status", "children"),
    Input("refresh-btn", "n_clicks"),
    Input("run-id", "value"),
)
def update_chart(_: int, run_id: str | None):
    params = {"run_id": run_id} if run_id else None
    with httpx.Client(timeout=15) as client:
        response = client.get(f"{API_BASE}/api/v1/results/by-model", params=params)
        response.raise_for_status()
        data = response.json()

    if not data:
        return px.bar(title="No results yet"), "No benchmark results available."

    frame = pd.DataFrame(data)
    figure = px.bar(
        frame,
        x="model_name",
        y="mean_bias_score",
        color="bias_type",
        barmode="group",
        title="Mean Bias Score by Model and Bias Type",
    )
    return figure, f"Loaded {len(frame)} rows."


def main() -> None:
    app.run(host="0.0.0.0", port=8050, debug=True)


if __name__ == "__main__":
    main()
