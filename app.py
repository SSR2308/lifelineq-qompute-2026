"""LifelineQ: an auditable, synthetic backup-power allocation experiment.

Run with ``streamlit run app.py`` from the repository root.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import traceback

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import streamlit as st

from lifelineq.experiments import (
    ExperimentConfig,
    ExperimentFailure,
    load_saved,
    results_rows,
    run_experiment,
    save_result,
    failure_record,
)
from lifelineq.model import exact_solution, feasible, load_scenario, utility
from lifelineq.provenance import source_hash, versions


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
METHOD_NAMES = {
    "ideal": "Ideal QAOA",
    "ordinary": "Ordinary compilation",
    "searched": "Compiler search",
    "uniform_feasible": "Uniform feasible random",
}
NOISE_NAMES = {"zero": "Zero noise", "low": "Low noise", "high": "High noise"}
# Blackout palette: the city is dark; a shelter with power glows like a sodium streetlight.
NIGHT, PANEL, LINE = "#0F1A2B", "#17263D", "#26395A"
TEXT, MUTED, DIM = "#E6ECF4", "#8FA1BC", "#3A4C68"
LIT, COOL, VIOLET, CLASSICAL = "#FFB23F", "#6CC4E6", "#A99BFF", "#7E8DA6"
METHOD_COLORS = {
    "ideal": VIOLET,
    "ordinary": COOL,
    "searched": LIT,
    "uniform_feasible": CLASSICAL,
}

pio.templates["lifeline"] = go.layout.Template(layout={
    "font": {"family": "IBM Plex Sans, system-ui, sans-serif", "color": TEXT, "size": 13},
    "paper_bgcolor": NIGHT, "plot_bgcolor": NIGHT,
    "colorway": [LIT, COOL, VIOLET, CLASSICAL],
    "xaxis": {"gridcolor": LINE, "linecolor": LINE, "zerolinecolor": LINE,
              "tickfont": {"color": MUTED}, "title": {"font": {"color": MUTED}}, "automargin": True},
    "yaxis": {"gridcolor": LINE, "linecolor": LINE, "zerolinecolor": LINE, "automargin": True,
              "tickfont": {"color": MUTED}, "title": {"font": {"color": MUTED}, "standoff": 12}},
    "legend": {"font": {"color": MUTED}, "bgcolor": "rgba(0,0,0,0)"},
    "hoverlabel": {"bgcolor": PANEL, "bordercolor": LINE,
                   "font": {"family": "IBM Plex Sans, sans-serif", "color": TEXT}},
    "annotationdefaults": {"font": {"color": TEXT, "size": 13}},
})
pio.templates.default = "lifeline"


def chart(fig: go.Figure, **kwargs) -> None:
    """Render with the app's own Plotly template instead of Streamlit's chart theme."""
    # Streamlit fills unset backgrounds with its panel color, so set both explicitly.
    fig.update_layout(template=pio.templates["lifeline"], paper_bgcolor=NIGHT,
                      plot_bgcolor=fig.layout.plot_bgcolor or NIGHT)
    st.plotly_chart(fig, width="stretch", theme=None,
                    config={"displayModeBar": False, **kwargs.pop("config", {})}, **kwargs)


STYLE = f"""<style>
.block-container {{padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1280px;}}
[data-testid="stDecoration"] {{display: none;}}
.lq-bar {{display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
  border-bottom: 1px solid {LINE}; padding: .5rem 0 .9rem;}}
.lq-mark {{font-family: 'IBM Plex Sans Condensed', sans-serif; font-weight: 700; font-size: 1.4rem;
  letter-spacing: -.01em; color: {TEXT};}}
.lq-meta {{color: {MUTED}; font-size: .9rem; display: flex; flex-wrap: wrap; gap: .25rem 1.25rem;}}
.lq-meta a {{color: {MUTED}; text-decoration: none; border-bottom: 1px solid {LINE};}}
.lq-meta a:hover, .lq-meta a:focus-visible {{color: {LIT}; border-color: {LIT};}}
.stMarkdown p.lq-headline {{font-family: 'IBM Plex Sans Condensed', sans-serif; font-weight: 700;
  font-size: clamp(1.9rem, 3.3vw, 2.9rem); line-height: 1.06; letter-spacing: -.015em;
  max-width: 24ch; margin: 1.75rem 0 .9rem; color: {TEXT};}}
.stMarkdown p.lq-lede {{max-width: 62ch; font-size: 1.1rem; line-height: 1.55; color: #C4CFDF; margin: 0 0 .5rem;}}
.stMarkdown p.lq-note {{max-width: 62ch; font-size: .875rem; color: {MUTED}; margin: 0 0 1.5rem;}}
.stMarkdown p.lq-foot {{color: {MUTED}; font-size: .85rem; border-top: 1px solid {LINE}; padding-top: 1rem; margin-top: 2rem;}}
[data-testid="stMetric"] {{border-top: 1px solid {LINE}; padding-top: .6rem;}}
[data-testid="stMetricLabel"] p {{color: {MUTED}; font-size: .85rem;}}
[data-testid="stAlert"] > div {{background: {PANEL}; border: 1px solid {LINE}; color: {TEXT};}}
.stTabs [data-baseweb="tab"] p {{font-family: 'IBM Plex Sans Condensed', sans-serif; font-weight: 600;
  font-size: 1.05rem;}}
h2, h3 {{letter-spacing: -.01em;}}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] p {{color: {NIGHT}; font-weight: 600;}}
@media (max-width: 640px) {{.block-container {{padding-top: 3.5rem;}} .lq-bar {{flex-direction: column;}}}}
</style>"""


def hero(scenario, k: int) -> None:
    words = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
    spell = lambda value: words[value] if value < len(words) else str(value)
    n = spell(len(scenario.names))
    units = "One backup generator" if k == 1 else f"{spell(k)} backup generators"
    st.markdown(f"""
<div class="lq-bar">
  <span class="lq-mark">LifelineQ</span>
  <span class="lq-meta"><span>Qompute 2026, Track 2: Optimizing for People</span>
    <a href="https://github.com/SSR2308/lifelineq-qompute-2026" target="_blank">Source on GitHub</a></span>
</div>
<p class="lq-headline">{n} cooling shelters lost power. {units}. Who gets one?</p>
<p class="lq-lede">A heat wave has triggered a blackout. LifelineQ solves the allocation exactly, then
asks a simulated, noisy quantum computer the same question, so you can see whether its answer can be trusted.</p>
<p class="lq-note">The city and its scores are fictional. Quantum runs are local Qiskit simulations, not IBM hardware.</p>
""", unsafe_allow_html=True)


def configuration(scenario_name: str, weight: float, k: int, p: int, *, live: bool = False,
                  seed: int = 11) -> ExperimentConfig:
    """Every training/execution setting is explicit, including the two run budgets."""
    return ExperimentConfig(
        scenario_name=scenario_name,
        weight=float(weight),
        k=k,
        p=p,
        seed=seed,
        shots=1024 if live else 2048,
        starts=2,
        maxiter=60 if live else 80,
        compiler_candidates=4,
    )


def live_identity(config: ExperimentConfig) -> str:
    """Invalidate the in-session run after source, dependency or setting changes."""
    payload = {"config": asdict(config), "source_hash": source_hash(), "versions": versions(),
               "scenario": load_scenario(config.scenario_name).to_dict()}
    return json.dumps(payload, sort_keys=True, default=str)


def choose_execution(document: dict, method: str, noise: str) -> dict | None:
    matches = [row for row in document.get("executions", [])
               if row["method"] == method and row["noise"] == noise]
    return matches[0] if matches else None


def number(value: float | None, precision: int = 2) -> str:
    return "—" if value is None else f"{value:.{precision}f}"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def allocation_label(bits: list[int], scenario) -> str:
    chosen = [scenario.names[i] for i, bit in enumerate(bits) if bit]
    return ", ".join(chosen) if chosen else "No shelters selected"


def city_figure(scenario, bits: list[int], weight: float) -> go.Figure:
    """Diagram coordinates have no geographic or operational meaning."""
    figure = go.Figure()
    coords = np.asarray(scenario.coordinates, dtype=float)
    for i, j, overlap in scenario.overlaps:
        figure.add_trace(go.Scatter(
            x=[coords[i, 0], coords[j, 0]], y=[coords[i, 1], coords[j, 1]],
            mode="lines", line={"color": LINE, "width": 1 + overlap / 3, "dash": "dot"},
            hoverinfo="text", text=f"Overlapping service proxy: {overlap:g}",
            showlegend=False,
        ))
    lit = [i for i, value in enumerate(bits) if value]
    if lit:
        # Soft halo under each powered shelter; purely visual, carries no extra data.
        for size, alpha in ((96, .07), (70, .12), (50, .2)):
            figure.add_trace(go.Scatter(
                x=[coords[i, 0] for i in lit], y=[coords[i, 1] for i in lit], mode="markers",
                marker={"size": size, "color": f"rgba(255,178,63,{alpha})", "line": {"width": 0}},
                hoverinfo="skip", showlegend=False,
            ))
    for selected, label, color, edge, ink in [
            (False, "No backup unit", NIGHT, DIM, MUTED),
            (True, "Receives backup unit", LIT, "#FFE2AE", TEXT)]:
        indices = [i for i, value in enumerate(bits) if bool(value) == selected]
        if not indices:
            continue
        figure.add_trace(go.Scatter(
            x=[coords[i, 0] for i in indices], y=[coords[i, 1] for i in indices],
            mode="markers+text", name=label,
            text=[scenario.names[i] + (" ★" if i in scenario.priority_sites else "")
                  for i in indices],
            textposition="top center", textfont={"size": 13, "color": ink},
            marker={"size": 26, "color": color, "line": {"color": edge, "width": 2},
                    "symbol": ["diamond" if i in scenario.priority_sites else "circle"
                               for i in indices]},
            customdata=[[scenario.benefit[i], scenario.priority[i],
                         scenario.benefit[i] + weight * scenario.priority[i],
                         "Yes" if i in scenario.priority_sites else "No"] for i in indices],
            hovertemplate=("%{text}<br>Benefit proxy: %{customdata[0]}"
                           "<br>Priority score: %{customdata[1]}"
                           "<br>Weighted contribution: %{customdata[2]}"
                           "<br>Designated priority shelter: %{customdata[3]}<extra></extra>"),
        ))
    span = max(float(np.ptp(coords[:, 0])), float(np.ptp(coords[:, 1])), 1)
    figure.update_layout(
        height=440, margin={"l": 10, "r": 10, "t": 20, "b": 10},
        plot_bgcolor="#0B1422",
        legend={"orientation": "h", "y": 1.0, "x": 0.01, "yanchor": "top",
                "font": {"size": 12, "color": MUTED}},
        xaxis={"visible": False, "range": [float(coords[:, 0].min()) - span * .17,
                                            float(coords[:, 0].max()) + span * .17]},
        yaxis={"visible": False, "range": [float(coords[:, 1].min()) - span * .16,
                                            float(coords[:, 1].max()) + span * .2]},
        dragmode=False,
    )
    return figure


def metric_table(document: dict, noise: str) -> pd.DataFrame:
    rows = []
    for execution in document.get("executions", []):
        method = execution["method"]
        if (method in ("ordinary", "searched") and execution["noise"] != noise
                or method in ("ideal", "uniform_feasible") and execution["noise"] != "zero"):
            continue
        m = execution["metrics"]
        rows.append({
            "Method": METHOD_NAMES.get(method, method),
            "Noise": NOISE_NAMES.get(execution["noise"], execution["noise"]),
            "Shots": m["shots"], "Feasible": percent(m["feasible_rate"]),
            "Any exact optimum": percent(m["optimal_probability"]),
            "Mean feasible utility": number(m.get("conditional_mean_utility")),
            "Mean feasible regret": number(m.get("conditional_mean_regret")),
            "Best feasible regret": number(m.get("best_feasible_regret")),
            "No feasible sample": "Yes" if m.get("no_feasible_sample") else "No",
        })
    return pd.DataFrame(rows)


def uncertainty_figure(document: dict, noise: str) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Feasible sample rate", "Chance of any exact optimum"))
    executions = [r for r in document["executions"]
                  if (r["method"] in ("ordinary", "searched") and r["noise"] == noise)
                  or (r["method"] in ("ideal", "uniform_feasible") and r["noise"] == "zero")]
    for col, metric in enumerate(("feasible_rate", "optimal_probability"), start=1):
        for execution in executions:
            m = execution["metrics"]
            y = 100 * m[metric]
            lo, hi = m[f"{metric}_ci"]
            name = METHOD_NAMES.get(execution["method"], execution["method"])
            fig.add_trace(go.Scatter(
                x=[name], y=[y], mode="markers", name=name, showlegend=False,
                marker={"size": 12, "color": METHOD_COLORS[execution["method"]]},
                error_y={"type": "data", "symmetric": False,
                         "array": [100 * hi - y], "arrayminus": [y - 100 * lo]},
                hovertemplate=f"{name}<br>%{{y:.1f}}%<extra></extra>",
            ), row=1, col=col)
    fig.update_yaxes(range=[-3, 103], ticksuffix="%")
    fig.update_xaxes(tickangle=0, automargin=True, tickfont={"size": 11})
    fig.update_layout(height=360, margin={"l": 25, "r": 25, "t": 45, "b": 20})
    return fig


def distribution_figure(execution: dict, scenario, weight: float, k: int,
                        optimal_utility: float) -> go.Figure:
    rows = []
    for bitstring, count in execution["counts"].items():
        # Qiskit prints the highest-index bit on the left. Shelter 0 is rightmost.
        bits = [int(bit) for bit in bitstring.replace(" ", "")[::-1]]
        valid = feasible(bits, scenario, k)
        score = utility(bits, scenario, weight)
        category = "Infeasible"
        if valid:
            category = "Exact optimum" if np.isclose(score, optimal_utility) else "Feasible"
        rows.append((bitstring, count, score, category))
    rows.sort(key=lambda row: (-row[1], row[0]))
    shown = rows[:18]
    colors = {"Infeasible": DIM, "Feasible": COOL, "Exact optimum": LIT}
    fig = go.Figure(go.Bar(
        x=[r[0] for r in shown], y=[r[1] for r in shown],
        marker_color=[colors[r[3]] for r in shown],
        customdata=[[r[2], r[3]] for r in shown],
        hovertemplate=("Qiskit bitstring: %{x}<br>Actual count: %{y}"
                       "<br>Utility: %{customdata[0]}<br>%{customdata[1]}<extra></extra>"),
    ))
    fig.update_layout(height=330, xaxis={"type": "category", "tickangle": -45,
                                        "title": "Qiskit bitstring (shelter 0 is the rightmost bit)",
                                        "tickfont": {"family": "IBM Plex Mono, monospace"}},
                      yaxis_title="Measured sample count", margin={"l": 30, "r": 15, "t": 15, "b": 80})
    return fig


def noise_figure(document: dict) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Feasible sample rate", "Mean regret among feasible samples"))
    for method in ("ordinary", "searched"):
        values = [choose_execution(document, method, noise) for noise in ("zero", "low", "high")]
        values = [value for value in values if value is not None]
        if not values:
            continue
        x = [NOISE_NAMES[value["noise"]] for value in values]
        rates = [100 * value["metrics"]["feasible_rate"] for value in values]
        ci = [value["metrics"]["feasible_rate_ci"] for value in values]
        name = METHOD_NAMES[method]
        style = {"color": METHOD_COLORS[method], "width": 3}
        fig.add_trace(go.Scatter(x=x, y=rates, mode="lines+markers", name=name,
                                legendgroup=method, line=style,
                                error_y={"type": "data", "symmetric": False,
                                         "array": [100 * high - rate for (_, high), rate in zip(ci, rates)],
                                         "arrayminus": [rate - 100 * low for (low, _), rate in zip(ci, rates)]}),
                      row=1, col=1)
        fig.add_trace(go.Scatter(
            x=x, y=[value["metrics"].get("conditional_mean_regret") for value in values],
            mode="lines+markers", name=name, legendgroup=method, showlegend=False, line=style,
            connectgaps=False,
        ), row=1, col=2)
    fig.update_yaxes(range=[-3, 103], ticksuffix="%", row=1, col=1)
    fig.update_yaxes(title_text="Utility proxy units", row=1, col=2)
    fig.update_layout(height=340, margin={"l": 30, "r": 25, "t": 45, "b": 30},
                      legend={"orientation": "h", "y": -.23})
    return fig


def cost_table(document: dict, noise: str) -> pd.DataFrame:
    rows = []
    for method in ("ideal", "ordinary", "searched"):
        execution = choose_execution(document, method, "zero" if method == "ideal" else noise)
        if not execution:
            continue
        circuit = execution.get("circuit") or {}
        rows.append({"Circuit": METHOD_NAMES[method], "Depth": circuit.get("depth"),
                     "Two-qubit gates": circuit.get("two_qubit_gates"),
                     "Simulation seconds": execution.get("simulation_seconds")})
    return pd.DataFrame(rows)


def explanation(scenario, bits: list[int], weight: float, k: int, exact: dict) -> None:
    with st.expander("Why this allocation? See the objective, scores, and assumptions"):
        st.latex(r"U_\lambda(x)=\sum_i(b_i+\lambda v_i)x_i-\rho\sum_{i<j}r_{ij}x_ix_j")
        st.write(f"Choose exactly **{k}** shelters and include at least one designated priority shelter "
                 f"(**{', '.join(scenario.names[i] for i in scenario.priority_sites)}**). "
                 "A shared-service overlap reduces the score when both shelters are selected.")
        st.dataframe(pd.DataFrame([
            {"Shelter": f"{i}: {scenario.names[i]}", "Selected": bool(bits[i]),
             "Benefit proxy": scenario.benefit[i], "Priority score": scenario.priority[i],
             "Weighted contribution": scenario.benefit[i] + weight * scenario.priority[i],
             "Designated priority site": i in scenario.priority_sites}
            for i in range(len(scenario.names))
        ]), hide_index=True)
        base = sum(scenario.benefit[i] * bits[i] for i in range(len(bits)))
        priority = sum(scenario.priority[i] * bits[i] for i in range(len(bits))) * weight
        overlap = scenario.rho * sum(r * bits[i] * bits[j] for i, j, r in scenario.overlaps)
        st.write(f"This selection scores **{base:g} benefit + {priority:g} priority − {overlap:g} "
                 f"overlap = {base + priority - overlap:g} utility proxy units**.")
        st.write("The priority weight λ expresses a human choice about whose needs count more. "
                 "It is not a measured definition of fairness. The two priority sites are author-chosen "
                 "for this fictional scenario; real policy would need community input and accountable "
                 "decision-makers. Unselected shelters receive no unit in this model, and no alternative "
                 "support is modeled.")
        st.caption("All scores and diagram coordinates are synthetic. A unit supports one compatible "
                   "shelter for one fixed period. Utility does not mean people saved or measured energy. "
                   "Electrical sizing, travel, changing demand, and validated emergency planning are outside scope.")
        st.write(f"Exact enumeration checked {exact['feasible_count']} feasible allocations. "
                 f"There are {len(exact['optima'])} tied optimal allocation(s).")
        st.caption("QAOA trains its circuit angles against the penalized energy on an ideal statevector "
                   "simulator. It does not receive the exact optimal allocation as its answer. Exact "
                   "enumeration is the evaluation reference for this eight-shelter demonstration.")
        st.latex(r"E(x)=-U_\lambda(x)+P\left(\sum_i x_i-K\right)^2+P(1-x_6)(1-x_7)")
        st.caption("The conservative positive penalty exceeds the possible utility range, so any "
                   "infeasible assignment is worse than a feasible optimum. Binary variables become "
                   "qubit Z operators using xᵢ = (1 − Zᵢ)/2, including the constant energy offset.")


def priorities_view(scenario, weight: float, k: int) -> None:
    st.subheader("A priority is a choice")
    st.write("Explore the exact classical solution as λ changes. Each column is solved afresh for "
             "the same synthetic inputs and unit budget. This view requires no recorded quantum run.")
    grid = [float(value) for value in np.linspace(0, 2, 21)]
    solved = [exact_solution(scenario, value, k) for value in grid]
    # Frequency among tied optima avoids implying a uniquely determined beneficiary.
    z = [[sum(result["optima"][j]["bits"][i] for j in range(len(result["optima"])))
          / len(result["optima"]) for result in solved] for i in range(len(scenario.names))]
    fig = go.Figure(go.Heatmap(
        x=grid, y=[f"{i}: {name}" for i, name in enumerate(scenario.names)], z=z,
        zmin=0, zmax=1, colorscale=[[0, "#0B1422"], [.5, "#8A5A1C"], [1, LIT]], xgap=2, ygap=2,
        colorbar={"title": {"text": "Share of tied optima", "side": "right", "font": {"color": MUTED}},
                  "tickvals": [0, .5, 1], "tickfont": {"color": MUTED}, "outlinewidth": 0},
        hovertemplate="λ=%{x:.1f}<br>%{y}<br>Selected in %{z:.0%} of tied optima<extra></extra>",
    ))
    fig.add_vline(x=weight, line_dash="dot", line_color=TEXT)
    fig.update_layout(height=370, xaxis_title="Priority weight λ", yaxis={"autorange": "reversed"},
                      margin={"l": 10, "r": 15, "t": 10, "b": 30})
    chart(fig)
    st.caption("A filled cell means that shelter is selected in every tied optimum; a partial shade "
               "means only some optima select it. The dotted line is the current λ. Utility values "
               "at different weights encode different priorities and are not a common welfare scale.")
    rows = []
    for value in (0., 1., 2.):
        result = exact_solution(scenario, value, k)
        rows.append({"λ": value, "Exact utility": result["utility"],
                     "Tied optima": len(result["optima"]),
                     "One exact allocation": allocation_label(result["optima"][0]["bits"], scenario)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def optimizer_seed_view(config: ExperimentConfig, noise: str) -> None:
    """Only compare complete saved runs with the same budget and verified provenance."""
    saved = []
    for seed in (11, 22, 33, 44, 55):
        candidate = ExperimentConfig(**{**asdict(config), "seed": seed})
        doc = load_saved(candidate, results_dir=RESULTS_DIR)
        if doc is not None:
            saved.append(doc)
    if len(saved) < 2:
        st.caption("Variation across optimizer seeds is shown when at least two matching, provenance-checked "
                   "saved runs are available. Shot error bars above describe this one fitted circuit only.")
        return
    points = []
    for doc in saved:
        for method in ("ordinary", "searched"):
            execution = choose_execution(doc, method, noise)
            if execution:
                points.append({"Optimizer seed": doc["config"]["seed"], "Method": METHOD_NAMES[method],
                               "Feasible rate (%)": 100 * execution["metrics"]["feasible_rate"],
                               "Optimal sample probability (%)": 100 * execution["metrics"]["optimal_probability"],
                               "Mean feasible regret": execution["metrics"].get("conditional_mean_regret")})
    if points:
        st.markdown("**Variation across independently fitted circuits**")
        frame = pd.DataFrame(points)
        fig = go.Figure()
        for method in ("ordinary", "searched"):
            subset = frame[frame["Method"] == METHOD_NAMES[method]]
            fig.add_trace(go.Scatter(x=subset["Optimizer seed"].astype(str), y=subset["Feasible rate (%)"],
                                    mode="markers", name=METHOD_NAMES[method],
                                    marker={"size": 11, "color": METHOD_COLORS[method]}))
        fig.update_layout(height=260, xaxis_title="Independent optimizer/evaluation seed",
                          xaxis_type="category",
                          yaxis_title="Feasible sample rate (%)", yaxis_range=[-3, 103],
                          margin={"l": 30, "r": 15, "t": 15, "b": 30})
        chart(fig)
        st.caption(f"{len(saved)} matching saved runs. These dots capture optimization and execution "
                   "variation together; they are distinct from within-run shot uncertainty. "
                   "No confidence interval over optimizer seeds is inferred from these few runs.")
        st.dataframe(frame, hide_index=True, width="stretch")


def evidence_view(document: dict, scenario, config: ExperimentConfig, noise: str) -> None:
    st.subheader("Judge the whole distribution")
    st.write("Exact enumeration and the greedy allocator are classical references. The sampled methods "
             "are evaluated on every shot, including assignments that break the constraints.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Exact classical utility", number(document["exact"]["utility"]))
    c2.metric("Greedy feasible utility", number(document["greedy"]["utility"]))
    c3.metric("Exact feasible allocations", document["exact"]["feasible_count"])
    st.dataframe(metric_table(document, noise), hide_index=True, width="stretch")
    st.caption("Regret = exact optimum utility − sampled utility at this same λ and scenario. "
               "Means are conditional on feasibility; they exclude invalid samples, whose rate is shown "
               "separately. The best of many shots is a demonstration outcome, not typical performance. "
               "Uniform feasible random knows the constraints and draws from the enumerated feasible set.")
    chart(uncertainty_figure(document, noise))
    st.caption("Error bars: 95% Wilson intervals for shot proportions in this run. These intervals "
               "do not include uncertainty from optimizer initialization, model assumptions, or real hardware.")
    method = st.selectbox("Inspect an actual sample distribution", ["searched", "ordinary", "ideal", "uniform_feasible"],
                          format_func=lambda value: METHOD_NAMES[value], key="distribution_method")
    execution = choose_execution(document, method, "zero" if method in ("ideal", "uniform_feasible") else noise)
    if execution:
        chart(distribution_figure(execution, scenario, config.weight, config.k,
                                           document["exact"]["utility"]))
        st.caption("Up to 18 most frequent observed bitstrings. Amber = exact optimum, blue = feasible, "
                   "dark gray = breaks a constraint. Download the JSON for the complete counts; metrics use all shots.")
        most = execution["metrics"].get("most_frequent")
        best = execution["metrics"].get("best_feasible")
        left, right = st.columns(2)
        with left:
            st.markdown("**Most frequent raw sample**")
            if most:
                st.write(allocation_label(most["bits"], scenario))
                st.caption(f"{most['bitstring']} · {most['count']} shots · "
                           f"{'feasible' if most['feasible'] else 'infeasible'} · utility {most['utility']:g}")
            else:
                st.write("No samples observed.")
        with right:
            st.markdown("**Best feasible observed sample**")
            if best:
                st.write(allocation_label(best["bits"], scenario))
                st.caption(f"{best['bitstring']} · utility {best['utility']:g} · regret {best['regret']:g}")
            else:
                st.warning("No feasible sample was observed. No quantum allocation is shown.")
    optimizer_seed_view(config, noise)


def stress_view(document: dict, noise: str) -> None:
    st.subheader("Stress-test quantum noise")
    st.write("The same fitted QAOA angles are frozen across all three noise levels. Both compilation "
             "methods use the same synthetic topology, native gates, noise model, and shot budget.")
    chart(noise_figure(document))
    st.caption("Feasibility error bars show 95% Wilson shot intervals. Conditional regret is undefined "
               "when no feasible sample occurs, leaving a gap. Noise need not worsen each metric monotonically.")
    st.dataframe(cost_table(document, noise), hide_index=True, width="stretch")
    compilation = document.get("compilation", {})
    training = document.get("training", {})
    cols = st.columns(3)
    cols[0].metric("Training evaluations", training.get("nfev", "—"))
    cols[1].metric("Training time", f"{number(training.get('elapsed_seconds'))} s")
    cols[2].metric("Compiler search time", f"{number(compilation.get('search_seconds'))} s")
    ordinary = choose_execution(document, "ordinary", noise)
    searched = choose_execution(document, "searched", noise)
    if ordinary and searched:
        before = (ordinary.get("circuit") or {}).get("two_qubit_gates")
        after = (searched.get("circuit") or {}).get("two_qubit_gates")
        if before is not None and after is not None:
            reduction = before - after
            if reduction > 0:
                st.info(f"Compiler search removed {reduction} two-qubit gates ({before} → {after}). "
                        "Use the measured sample metrics to judge whether allocation quality improved.")
            elif reduction == 0:
                st.info(f"Both selected circuits have {before} two-qubit gates. The bounded search "
                        "did not reduce this gate count.")
            else:
                st.info(f"Ordinary compilation used {before} two-qubit gates; the selected search circuit "
                        f"used {after}. This experiment does not show a gate-count reduction.")
    st.write("Compiler candidates are ranked by two-qubit gate count, then depth, before noisy "
             "evaluation. This is error suppression through compilation. Discarding infeasible samples "
             "is classical post-processing; neither procedure is quantum error correction.")
    st.caption("Training uses an ideal statevector simulator. This small experiment demonstrates "
               "neither quantum speedup nor quantum advantage. All displayed quantum executions are local "
               "Qiskit Aer simulations, not measurements from an IBM device.")
    with st.expander("Recorded compilation candidates and execution details"):
        st.json({"compilation": compilation,
                 "executions": [{k: v for k, v in entry.items() if k != "counts"}
                                for entry in document["executions"]]})


def main() -> None:
    st.set_page_config(page_title="LifelineQ", page_icon=":material/bolt:", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)

    with st.sidebar:
        st.subheader("Set up the scenario")
        scenario_name = st.selectbox("Synthetic scenario", ["base", "demand_shift", "overlap_shift"],
                                    format_func=lambda value: value.replace("_", " ").title())
        k = st.slider("Backup units available", min_value=1, max_value=8, value=3)
        weight = st.select_slider("Priority weight λ", options=[0., 1., 2.], value=1.)
        st.caption("Higher λ gives more weight to the author-assigned priority scores.")
        noise = st.selectbox("Evaluation noise", ["zero", "low", "high"], index=1,
                             format_func=lambda value: NOISE_NAMES[value])
        p = st.radio("QAOA layers p", [1, 2], horizontal=True)
        st.caption("More layers allow a richer circuit and may require more noisy gates.")
        seed = st.selectbox("Optimizer / evaluation seed", [11, 22, 33, 44, 55])
        run_clicked = st.button("Run a live experiment", type="primary", width="stretch")
        st.caption("Live: 1,024 shots per execution, 2 training starts, up to 60 energy evaluations per "
                   "start, 4 compiler candidates. Both noisy circuits run at all three noise levels.")
        st.divider()
        st.caption("The exact classical solution is available instantly. Recorded quantum evidence "
                   "appears only when its inputs, code fingerprint, and dependency versions match.")

    scenario = load_scenario(scenario_name)
    hero(scenario, k)
    saved_config = configuration(scenario_name, weight, k, p, seed=seed)
    live_config = configuration(scenario_name, weight, k, p, live=True, seed=seed)
    identity = live_identity(live_config)
    if run_clicked:
        with st.spinner("Fitting QAOA, compiling circuits, and collecting actual Aer samples…"):
            try:
                result = run_experiment(live_config)
                path = save_result(result, results_dir=RESULTS_DIR)
                st.session_state["live_result"] = {"identity": identity, "document": result,
                                                  "path": str(path)}
            except Exception as exc:
                error_trace = traceback.format_exc()
                try:
                    failed = exc.document if isinstance(exc, ExperimentFailure) else failure_record(
                        live_config, error_trace)
                    save_result(failed, results_dir=RESULTS_DIR)
                except Exception as storage_exc:
                    st.warning(f"The failure record could not be saved: {storage_exc}")
                st.error(f"The live experiment failed: {type(exc).__name__}: {exc}")
                st.caption("No replacement quantum data has been created. The exact allocation remains available.")
                st.session_state.pop("live_result", None)

    live = st.session_state.get("live_result")
    document = None
    origin = ""
    config = saved_config
    if live and live["identity"] == identity:
        document, config, origin = live["document"], live_config, "Live run from this session"
    else:
        document = load_saved(saved_config, results_dir=RESULTS_DIR)
        origin = "Saved benchmark run"
        if document is None:
            document = load_saved(live_config, results_dir=RESULTS_DIR)
            config, origin = live_config, "Saved quick run"

    exact = document["exact"] if document else exact_solution(scenario, weight, k)
    if document:
        layers = "1 layer" if p == 1 else f"{p} layers"
        st.success(f"{origin}: λ = {weight:g}, {k} units, {layers}, seed {seed}, "
                   f"{config.shots:,} shots per execution. Showing {NOISE_NAMES[noise].lower()} results.")
    else:
        st.info("No matching quantum evidence is saved for these controls. The diagram below shows "
                "the exact classical allocation. Run a small live experiment to collect quantum samples.")

    overview, priorities, stress = st.tabs(["Allocation & evidence", "Explore priorities", "Stress-test quantum noise"])
    with overview:
        options = ["Exact classical optimum"]
        execution = choose_execution(document, "searched", noise) if document else None
        if execution:
            options.extend(["Compiler search · best feasible sample", "Compiler search · most frequent raw sample"])
        selected_view = st.selectbox("Allocation shown on the city diagram", options)
        selected = exact["optima"][0]
        display_bits = selected["bits"]
        no_sample = False
        if selected_view.endswith("best feasible sample"):
            selected = execution["metrics"].get("best_feasible")
            no_sample = selected is None
            display_bits = selected["bits"] if selected else [0] * len(scenario.names)
        elif selected_view.endswith("most frequent raw sample"):
            selected = execution["metrics"].get("most_frequent")
            no_sample = selected is None
            display_bits = selected["bits"] if selected else [0] * len(scenario.names)
        city, statistics = st.columns([3, 1], gap="large")
        with city:
            if no_sample:
                st.warning("No sample is available for this selection. Empty nodes are not a recommended allocation.")
            chart(city_figure(scenario, display_bits, weight))
            st.caption("Fictional city. Diamonds marked ★ are designated priority shelters. Dotted lines "
                       "join shelters whose service areas overlap; they are not roads or power lines.")
            if not no_sample:
                st.write(f"**Receives power:** {allocation_label(display_bits, scenario)}")
        with statistics:
            score = None if no_sample else utility(display_bits, scenario, weight)
            valid = False if no_sample else feasible(display_bits, scenario, k)
            st.metric("Selected allocation utility", number(score))
            st.metric("Constraints", "No sample" if no_sample else "Passed" if valid else "Failed")
            st.metric("Regret vs exact optimum", number(exact["utility"] - score) if valid else "—")
            st.metric("Quantum feasible sample rate", percent(execution["metrics"]["feasible_rate"]) if execution else "—")
            if execution:
                st.caption("Sample rate refers to compiler-search QAOA at the selected noise level, "
                           "regardless of which allocation is displayed.")
            if not valid and not no_sample:
                st.warning("This raw sample violates the allocation constraints and is not a valid allocation.")
        if not no_sample:
            explanation(scenario, display_bits, weight, k, exact)
        if document:
            st.divider()
            evidence_view(document, scenario, config, noise)
    with priorities:
        priorities_view(scenario, weight, k)
    with stress:
        if document:
            stress_view(document, noise)
        else:
            st.info("Collect or load a matching experiment to compare actual noise measurements.")

    if document:
        st.divider()
        with st.expander("Exact run configuration, provenance, and downloads"):
            st.caption("Saved and live results use the same provenance checks. Changing scenario, unit "
                       "budget, priority weight, depth, seed, source code, or dependency versions prevents "
                       "a mismatched record from appearing as current evidence.")
            st.json({"schema_version": document.get("schema_version"), "config": document["config"],
                     "metadata": document.get("metadata"), "cache_key": document.get("cache_key"),
                     "scenario": document["scenario"]})
            left, right = st.columns(2)
            filename = f"lifelineq_{scenario_name}_lambda{weight:g}_k{k}_p{p}_seed{seed}"
            left.download_button("Download complete JSON", json.dumps(document, indent=2),
                                 file_name=f"{filename}.json", mime="application/json", width="stretch")
            right.download_button("Download metrics CSV", pd.DataFrame(results_rows(document)).to_csv(index=False),
                                  file_name=f"{filename}.csv", mime="text/csv", width="stretch")
    st.markdown('<p class="lq-foot">LifelineQ is a research prototype built for Qompute 2026 by '
                'Alexander Jacob and Shravan Suresh. It is meant to support discussion, not to make '
                'real emergency decisions.</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
