"""Live six-panel dashboard backed by the structured JSONL request log."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml


ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config/dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
PANELS = {panel["id"]: panel for panel in CONFIG["panels"]}
LOG_PATH = ROOT / PANELS["latency"]["source"]


@st.cache_data(ttl=5, max_entries=2)
def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
        except json.JSONDecodeError:
            continue
    frame = pd.DataFrame(records)
    if frame.empty or "ts" not in frame:
        return pd.DataFrame()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    return frame.dropna(subset=["ts"])


def windowed_logs(frame: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame
    end = now or datetime.now(timezone.utc)
    return frame.loc[
        (frame["ts"] >= end - timedelta(minutes=CONFIG["time_range_minutes"]))
        & (frame["ts"] <= end)
    ].copy()


def series(frame: pd.DataFrame, event: str, field: str, aggregation: str) -> pd.DataFrame:
    selected = frame.loc[frame["event"] == event, ["ts", field]].copy()
    if selected.empty:
        return pd.DataFrame(columns=["minute", "value"])
    selected[field] = pd.to_numeric(selected[field], errors="coerce")
    selected["minute"] = selected["ts"].dt.floor("min")
    grouped = selected.groupby("minute")[field]
    if aggregation == "sum":
        values = grouped.sum()
    elif aggregation == "mean":
        values = grouped.mean()
    elif aggregation == "p95":
        values = grouped.quantile(0.95)
    else:
        raise ValueError(aggregation)
    return values.rename("value").reset_index()


def chart(data: pd.DataFrame, panel_id: str, color: str = "#2563eb") -> None:
    panel = PANELS[panel_id]
    limit = panel["threshold"]["value"]
    st.caption(
        f"Unit: {panel['unit']} · 60 min · threshold "
        f"{panel['threshold']['operator']} {limit} ({panel['threshold']['aggregation']})"
    )
    if data.empty:
        st.info("No observations in the last 60 minutes.")
        return
    plot = (
        alt.Chart(data)
        .mark_line(point=True, color=color)
        .encode(
            x=alt.X("minute:T", title="Time (UTC)"),
            y=alt.Y("value:Q", title=panel["unit"]),
            tooltip=["minute:T", alt.Tooltip("value:Q", format=".3f")],
        )
    )
    threshold = alt.Chart(pd.DataFrame({"threshold": [limit]})).mark_rule(
        color="#dc2626", strokeDash=[6, 4]
    ).encode(y="threshold:Q")
    st.altair_chart(plot + threshold)


def numeric(frame: pd.DataFrame, field: str) -> pd.Series:
    return pd.to_numeric(frame.get(field, pd.Series(dtype=float)), errors="coerce").dropna()


@st.fragment(run_every=CONFIG["refresh_seconds"])
def render_dashboard() -> None:
    frame = windowed_logs(load_logs())
    if frame.empty:
        st.warning(f"No log records in the last 60 minutes: {LOG_PATH}")
        return
    requests = frame.loc[frame["event"] == "request_received"]
    responses = frame.loc[frame["event"] == "response_sent"]
    failures = frame.loc[frame["event"] == "request_failed"]
    st.caption(
        f"Source: {LOG_PATH.relative_to(ROOT)} · "
        f"{len(frame)} events · last event {frame['ts'].max():%Y-%m-%d %H:%M:%S} UTC · "
        f"refresh every {CONFIG['refresh_seconds']} s"
    )

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader(PANELS["latency"]["title"])
        latency = numeric(responses, "latency_ms")
        ttft = numeric(responses, "ttft_ms")
        with st.container(horizontal=True):
            for label, values, quantile in (
                ("P50", latency, 0.50), ("P95", latency, 0.95),
                ("P99", latency, 0.99), ("TTFT P95", ttft, 0.95),
            ):
                st.metric(label, f"{values.quantile(quantile):.0f} ms" if not values.empty else "—")
        chart(series(frame, "response_sent", "latency_ms", "p95"), "latency")

    with right, st.container(border=True):
        st.subheader(PANELS["traffic"]["title"])
        st.metric("Requests / 60 min", len(requests))
        traffic = requests.assign(minute=requests["ts"].dt.floor("min"))
        traffic = traffic.groupby("minute").size().rename("value").reset_index()
        chart(traffic, "traffic")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader(PANELS["errors"]["title"])
        rate = len(failures) / len(requests) * 100 if len(requests) else 0.0
        tool_events = frame.loc[frame["tool_success"].notna()] if "tool_success" in frame else frame.iloc[:0]
        success = (tool_events["tool_success"].eq(True).mean() * 100) if len(tool_events) else 0.0
        with st.container(horizontal=True):
            st.metric("Error rate", f"{rate:.1f}%")
            st.metric("Retrieval success", f"{success:.1f}%" if len(tool_events) else "—")
        if not failures.empty:
            st.caption("Error breakdown")
            st.dataframe(failures["error_type"].fillna("unknown").value_counts().rename_axis("type").reset_index(name="count"), hide_index=True)
        counts = frame.loc[frame["event"].isin(["request_received", "request_failed"])].copy()
        counts["minute"] = counts["ts"].dt.floor("min")
        counts = counts.groupby(["minute", "event"]).size().unstack(fill_value=0)
        for event in ("request_received", "request_failed"):
            if event not in counts:
                counts[event] = 0
        error_series = (counts["request_failed"] / counts["request_received"].replace(0, pd.NA) * 100).fillna(0).rename("value").reset_index()
        chart(error_series, "errors", "#dc2626")

    with right, st.container(border=True):
        st.subheader(PANELS["cost"]["title"])
        st.metric("Total cost / 60 min", f"${numeric(responses, 'cost_usd').sum():.4f}")
        cost_series = series(frame, "response_sent", "cost_usd", "sum")
        if not cost_series.empty:
            cost_series["value"] = cost_series["value"].cumsum()
        st.caption("Cumulative cost within the 60-minute window")
        chart(cost_series, "cost", "#7c3aed")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader(PANELS["tokens"]["title"])
        token_in = numeric(responses, "tokens_in").sum()
        token_out = numeric(responses, "tokens_out").sum()
        with st.container(horizontal=True):
            st.metric("Input tokens", f"{token_in:,.0f}")
            st.metric("Output tokens", f"{token_out:,.0f}")
        token_series = series(frame, "response_sent", "tokens_in", "sum")
        other = series(frame, "response_sent", "tokens_out", "sum")
        if not token_series.empty or not other.empty:
            combined = token_series.rename(columns={"value": "Input"}).merge(
                other.rename(columns={"value": "Output"}), on="minute", how="outer"
            ).fillna(0)
            token_series = combined.assign(value=combined["Input"] + combined["Output"])[["minute", "value"]]
            token_series["value"] = token_series["value"].cumsum()
        st.caption("Cumulative input + output tokens within the 60-minute window")
        chart(token_series, "tokens", "#0891b2")

    with right, st.container(border=True):
        st.subheader(PANELS["quality"]["title"])
        quality = numeric(responses, "quality_score")
        st.metric("Mean quality proxy", f"{quality.mean():.2f}" if not quality.empty else "—")
        chart(series(frame, "response_sent", "quality_score", "mean"), "quality", "#059669")


st.set_page_config(page_title=CONFIG["title"], layout="wide")
st.title(CONFIG["title"])
st.caption("Metrics → Logs → Traces · 6 panels · 60-minute sliding window")
render_dashboard()
