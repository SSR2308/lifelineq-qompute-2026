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
    "ideal": "QAOA, no noise",
    "ordinary": "QAOA, standard compile",
    "searched": "QAOA, optimized compile",
    "uniform_feasible": "Random valid pick",
}
NOISE_NAMES = {"zero": "No noise", "low": "Low noise", "high": "High noise"}
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
            hoverinfo="text", text=f"Overlap: {overlap:g}",
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
            (False, "No power", NIGHT, DIM, MUTED),
            (True, "Gets a generator", LIT, "#FFE2AE", TEXT)]:
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
            hovertemplate=("%{text}<br>Benefit: %{customdata[0]}"
                           "<br>Priority: %{customdata[1]}"
                           "<br>Weighted score: %{customdata[2]}"
                           "<br>Priority shelter: %{customdata[3]}<extra></extra>"),
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


def metric_table(document: dict, noise: str, *, full: bool = False) -> pd.DataFrame:
    rows = []
    for execution in document.get("executions", []):
        method = execution["method"]
        if (method in ("ordinary", "searched") and execution["noise"] != noise
                or method in ("ideal", "uniform_feasible") and execution["noise"] != "zero"):
            continue
        m = execution["metrics"]
        row = {
            "Method": METHOD_NAMES.get(method, method),
            "Noise": NOISE_NAMES.get(execution["noise"], execution["noise"]),
            "Valid answers": percent(m["feasible_rate"]),
            "Hit the best answer": percent(m["optimal_probability"]),
            "Avg points short (valid only)": number(m.get("conditional_mean_regret")),
        }
        if full:
            row.update({
                "Shots": m["shots"],
                "Avg score (valid only)": number(m.get("conditional_mean_utility")),
                "Best valid answer, points short": number(m.get("best_feasible_regret")),
                "No valid answer at all": "Yes" if m.get("no_feasible_sample") else "No",
            })
        rows.append(row)
    return pd.DataFrame(rows)


def uncertainty_figure(document: dict, noise: str) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Valid answers", "Hit the best answer"))
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
                x=[name.replace(", ", "<br>")], y=[y], mode="markers", name=name, showlegend=False,
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
        category = "Breaks the rules"
        if valid:
            category = "Best possible" if np.isclose(score, optimal_utility) else "Valid"
        rows.append((bitstring, count, score, category))
    rows.sort(key=lambda row: (-row[1], row[0]))
    shown = rows[:18]
    colors = {"Breaks the rules": DIM, "Valid": COOL, "Best possible": LIT}
    fig = go.Figure(go.Bar(
        x=[r[0] for r in shown], y=[r[1] for r in shown],
        marker_color=[colors[r[3]] for r in shown],
        customdata=[[r[2], r[3]] for r in shown],
        hovertemplate=("%{x}<br>Picked %{y} times<br>Score %{customdata[0]}"
                       "<br>%{customdata[1]}<extra></extra>"),
    ))
    fig.update_layout(height=330, xaxis={"type": "category", "tickangle": -45,
                                        "title": "Answer as bits (rightmost bit is shelter 0)",
                                        "tickfont": {"family": "IBM Plex Mono, monospace"}},
                      yaxis_title="Times picked", margin={"l": 30, "r": 15, "t": 15, "b": 80})
    return fig


def noise_figure(document: dict) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Valid answers", "Avg points short (valid answers only)"))
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
    fig.update_yaxes(title_text="Points", row=1, col=2)
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
        seconds = execution.get("simulation_seconds")
        rows.append({"Circuit": METHOD_NAMES[method], "Depth": circuit.get("depth"),
                     "Two-qubit gates": circuit.get("two_qubit_gates"),
                     "Simulation time (s)": None if seconds is None else round(seconds, 3)})
    return pd.DataFrame(rows)


def explanation(scenario, bits: list[int], weight: float, k: int, exact: dict) -> None:
    with st.expander("How the score works"):
        st.latex(r"U_\lambda(x)=\sum_i(b_i+\lambda v_i)x_i-\rho\sum_{i<j}r_{ij}x_ix_j")
        st.write(f"Each shelter has a benefit score and a priority score. λ sets how much the priority "
                 f"score counts. Two shelters that serve the same area lose points when both are picked. "
                 f"A valid answer picks exactly {k} shelters, including at least one of "
                 f"{' or '.join(scenario.names[i] for i in scenario.priority_sites)}.")
        st.dataframe(pd.DataFrame([
            {"Shelter": scenario.names[i], "Gets power": bool(bits[i]),
             "Benefit": scenario.benefit[i], "Priority": scenario.priority[i],
             "Weighted score": round(scenario.benefit[i] + weight * scenario.priority[i], 2),
             "Priority shelter": i in scenario.priority_sites}
            for i in range(len(scenario.names))
        ]), hide_index=True)
        base = sum(scenario.benefit[i] * bits[i] for i in range(len(bits)))
        priority = sum(scenario.priority[i] * bits[i] for i in range(len(bits))) * weight
        overlap = scenario.rho * sum(r * bits[i] * bits[j] for i, j, r in scenario.overlaps)
        st.write(f"This pick scores **{base:g} benefit + {priority:g} priority − {overlap:g} overlap "
                 f"= {base + priority - overlap:g} points**. We checked all {exact['feasible_count']} valid "
                 f"picks; {len(exact['optima'])} of them tie for the best score.")
        st.write("For the quantum circuit, the rules become penalties, so any answer that breaks them "
                 "scores worse than any answer that follows them:")
        st.latex(r"E(x)=-U_\lambda(x)+P\left(\sum_i x_i-K\right)^2+P(1-x_6)(1-x_7)")


def priorities_view(scenario, weight: float, k: int) -> None:
    st.subheader("A priority is a choice")
    st.write("Change λ and the best answer changes. Each column below is the exact best allocation "
             "at that weight.")
    grid = [float(value) for value in np.linspace(0, 2, 21)]
    solved = [exact_solution(scenario, value, k) for value in grid]
    # Frequency among tied optima avoids implying a uniquely determined beneficiary.
    z = [[sum(result["optima"][j]["bits"][i] for j in range(len(result["optima"])))
          / len(result["optima"]) for result in solved] for i in range(len(scenario.names))]
    fig = go.Figure(go.Heatmap(
        x=grid, y=list(scenario.names), z=z,
        zmin=0, zmax=1, colorscale=[[0, "#0B1422"], [.5, "#8A5A1C"], [1, LIT]], xgap=2, ygap=2,
        colorbar={"title": {"text": "Share of tied best answers", "side": "right", "font": {"color": MUTED}},
                  "tickvals": [0, .5, 1], "tickfont": {"color": MUTED}, "outlinewidth": 0},
        hovertemplate="λ=%{x:.1f}<br>%{y}<br>Gets power in %{z:.0%} of best answers<extra></extra>",
    ))
    fig.add_vline(x=weight, line_dash="dot", line_color=TEXT)
    fig.update_layout(height=370, xaxis_title="Priority weight λ", yaxis={"autorange": "reversed"},
                      margin={"l": 10, "r": 15, "t": 10, "b": 30})
    chart(fig)
    st.caption("Bright means the shelter gets power in every best answer; half-lit means only in some "
               "of the tied ones. The dotted line is your current λ.")
    never = [scenario.names[i] for i in range(len(scenario.names)) if max(row for row in z[i]) == 0]
    if never:
        st.markdown(f"**Never powered at any weight from 0 to 2:** {', '.join(never)}.")
    rows = []
    for value in (0., 1., 2.):
        result = exact_solution(scenario, value, k)
        rows.append({"λ": value, "Best score": result["utility"],
                     "Tied best answers": len(result["optima"]),
                     "One best answer": allocation_label(result["optima"][0]["bits"], scenario)})
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
        return
    points = []
    for doc in saved:
        for method in ("ordinary", "searched"):
            execution = choose_execution(doc, method, noise)
            if execution:
                regret = execution["metrics"].get("conditional_mean_regret")
                points.append({"Seed": doc["config"]["seed"], "Method": METHOD_NAMES[method],
                               "Valid answers (%)": round(100 * execution["metrics"]["feasible_rate"], 1),
                               "Hit the best answer (%)": round(100 * execution["metrics"]["optimal_probability"], 1),
                               "Avg points short": None if regret is None else round(regret, 2)})
    if points:
        with st.expander(f"Does it change between runs? ({len(saved)} saved runs)"):
            frame = pd.DataFrame(points)
            fig = go.Figure()
            for method in ("ordinary", "searched"):
                subset = frame[frame["Method"] == METHOD_NAMES[method]]
                fig.add_trace(go.Scatter(x=subset["Seed"].astype(str), y=subset["Valid answers (%)"],
                                        mode="markers", name=METHOD_NAMES[method],
                                        marker={"size": 11, "color": METHOD_COLORS[method]}))
            fig.update_layout(height=260, xaxis_title="Run seed", xaxis_type="category",
                              yaxis_title="Valid answers (%)", yaxis_range=[-3, 103],
                              margin={"l": 30, "r": 15, "t": 15, "b": 30})
            chart(fig)
            st.caption("Each dot is a separately trained circuit. The spread shows how much results "
                       "depend on the starting point.")
            st.dataframe(frame, hide_index=True, width="stretch")


def evidence_view(document: dict, scenario, config: ExperimentConfig, noise: str) -> None:
    st.subheader("How did the quantum computer do?")
    st.write("We checked every answer the circuit gave, including the ones that break the rules, "
             "against the exact best answer and two simple classical methods.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Best possible score", number(document["exact"]["utility"], 0))
    c2.metric("Greedy method's score", number(document["greedy"]["utility"], 0))
    c3.metric("Valid picks to choose from", document["exact"]["feasible_count"])
    st.dataframe(metric_table(document, noise), hide_index=True, width="stretch")
    chart(uncertainty_figure(document, noise))
    st.caption("Whiskers show the 95% confidence range for this run.")
    with st.expander("See the raw quantum answers"):
        method = st.selectbox("Answers from", ["searched", "ordinary", "ideal", "uniform_feasible"],
                              format_func=lambda value: METHOD_NAMES[value], key="distribution_method")
        execution = choose_execution(document, method, "zero" if method in ("ideal", "uniform_feasible") else noise)
        if execution:
            chart(distribution_figure(execution, scenario, config.weight, config.k,
                                      document["exact"]["utility"]))
            st.caption("The 18 most common answers. Amber is a best possible answer, blue is valid, "
                       "gray breaks the rules.")
            most = execution["metrics"].get("most_frequent")
            best = execution["metrics"].get("best_feasible")
            left, right = st.columns(2)
            with left:
                st.markdown("**Most common answer**")
                if most:
                    st.write(allocation_label(most["bits"], scenario))
                    status = "valid" if most["feasible"] else "breaks the rules"
                    st.caption(f"Picked {most['count']} times, {status}, score {most['utility']:g}")
                else:
                    st.write("No answers recorded.")
            with right:
                st.markdown("**Best valid answer**")
                if best:
                    st.write(allocation_label(best["bits"], scenario))
                    st.caption(f"Score {best['utility']:g}, {best['regret']:g} points short of the best")
                else:
                    st.warning("The circuit never gave a valid answer, so there is nothing to show.")
    with st.expander("See the full numbers"):
        st.dataframe(metric_table(document, noise, full=True), hide_index=True, width="stretch")
    optimizer_seed_view(config, noise)


def stress_view(document: dict, noise: str) -> None:
    st.subheader("Stress-test quantum noise")
    st.write("We trained the circuit once, froze it, and ran it at three noise levels: once with a "
             "standard compile and once with the best of four compiles.")
    chart(noise_figure(document))
    st.caption("Whiskers show the 95% confidence range. A gap means the circuit gave no valid answer.")
    ordinary = choose_execution(document, "ordinary", noise)
    searched = choose_execution(document, "searched", noise)
    if ordinary and searched:
        before = (ordinary.get("circuit") or {}).get("two_qubit_gates")
        after = (searched.get("circuit") or {}).get("two_qubit_gates")
        if before is not None and after is not None:
            if before > after:
                st.info(f"Optimized compiling cut two-qubit gates from {before} to {after}. "
                        "Compare the lines above to see whether the answers got better.")
            elif before == after:
                st.info(f"Both compiles used {before} two-qubit gates, so the search found nothing smaller.")
            else:
                st.info(f"The standard compile used {before} two-qubit gates and the optimized one "
                        f"used {after}, so the search didn't help here.")
    with st.expander("Circuit size and timing"):
        st.dataframe(cost_table(document, noise), hide_index=True, width="stretch")
        compilation = document.get("compilation", {})
        training = document.get("training", {})
        cols = st.columns(3)
        cols[0].metric("Training steps", training.get("nfev", "—"))
        cols[1].metric("Training time", f"{number(training.get('elapsed_seconds'))} s")
        cols[2].metric("Compile search time", f"{number(compilation.get('search_seconds'))} s")
        st.caption("Fewer two-qubit gates means fewer chances for noise to flip a bit. Neither compile "
                   "is error correction.")
    with st.expander("Compile candidates (raw data)"):
        st.json({"compilation": document.get("compilation", {}),
                 "executions": [{k: v for k, v in entry.items() if k != "counts"}
                                for entry in document["executions"]]})


VIEW_EXACT = "Best possible (exact)"
VIEW_BEST = "Quantum: best valid answer"
VIEW_COMMON = "Quantum: most common answer"


def main() -> None:
    st.set_page_config(page_title="LifelineQ", page_icon=":material/bolt:", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)

    with st.sidebar:
        st.subheader("Set up the scenario")
        scenario_name = st.selectbox("Scenario", ["base", "demand_shift", "overlap_shift"],
                                    format_func=lambda value: value.replace("_", " ").capitalize())
        k = st.slider("Backup generators", min_value=1, max_value=8, value=3)
        weight = st.select_slider("Priority weight (λ)", options=[0., 1., 2.], value=1.)
        st.caption("How much extra weight high-need shelters get.")
        noise = st.selectbox("Quantum noise level", ["zero", "low", "high"], index=1,
                             format_func=lambda value: NOISE_NAMES[value])
        p = st.radio("Circuit layers", [1, 2], horizontal=True)
        seed = st.selectbox("Run seed", [11, 22, 33, 44, 55])
        run_clicked = st.button("Run a live experiment", type="primary", width="stretch")
        st.caption("Runs a smaller version (1,024 shots) right now on this computer.")

    scenario = load_scenario(scenario_name)
    hero(scenario, k)
    saved_config = configuration(scenario_name, weight, k, p, seed=seed)
    live_config = configuration(scenario_name, weight, k, p, live=True, seed=seed)
    identity = live_identity(live_config)
    if run_clicked:
        with st.spinner("Training the circuit and running it at three noise levels…"):
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
                st.session_state.pop("live_result", None)

    live = st.session_state.get("live_result")
    document = None
    origin = ""
    config = saved_config
    if live and live["identity"] == identity:
        document, config, origin = live["document"], live_config, "Live run"
    else:
        document = load_saved(saved_config, results_dir=RESULTS_DIR)
        origin = "Saved run"
        if document is None:
            document = load_saved(live_config, results_dir=RESULTS_DIR)
            config, origin = live_config, "Saved quick run"

    exact = document["exact"] if document else exact_solution(scenario, weight, k)
    if document:
        layers = "1 layer" if p == 1 else f"{p} layers"
        st.success(f"{origin}: λ = {weight:g}, {k} generators, {layers}, seed {seed}, "
                   f"{config.shots:,} shots. Showing {NOISE_NAMES[noise].lower()}.")
    else:
        st.info("No saved quantum run matches these settings. The map shows the exact best answer. "
                "Press Run a live experiment to get quantum results.")

    overview, priorities, stress = st.tabs(["Allocation & evidence", "Explore priorities", "Stress-test quantum noise"])
    with overview:
        options = [VIEW_EXACT]
        execution = choose_execution(document, "searched", noise) if document else None
        if execution:
            options.extend([VIEW_BEST, VIEW_COMMON])
        selected_view = st.selectbox("Show on the map", options)
        selected = exact["optima"][0]
        display_bits = selected["bits"]
        no_sample = False
        if selected_view in (VIEW_BEST, VIEW_COMMON):
            key = "best_feasible" if selected_view == VIEW_BEST else "most_frequent"
            selected = execution["metrics"].get(key)
            no_sample = selected is None
            display_bits = selected["bits"] if selected else [0] * len(scenario.names)
        city, statistics = st.columns([3, 1], gap="large")
        with city:
            if no_sample:
                st.warning("The quantum circuit gave no valid answer here, so the map is empty.")
            chart(city_figure(scenario, display_bits, weight))
            st.caption("Fictional city. ★ marks a priority shelter; at least one must get power. Dotted "
                       "lines join shelters that serve overlapping areas.")
            if not no_sample:
                st.write(f"**Gets power:** {allocation_label(display_bits, scenario)}")
        with statistics:
            score = None if no_sample else utility(display_bits, scenario, weight)
            valid = False if no_sample else feasible(display_bits, scenario, k)
            st.metric("Score", number(score, 0))
            st.metric("Follows the rules", "No answer" if no_sample else "Yes" if valid else "No")
            st.metric("Points short of best", number(exact["utility"] - score, 0) if valid else "—")
            st.metric("Valid quantum answers",
                      percent(execution["metrics"]["feasible_rate"]) if execution else "—",
                      help="Share of the quantum circuit's answers (optimized compile, chosen noise "
                           "level) that follow the rules.")
            if not valid and not no_sample:
                st.warning("This answer breaks the rules, so it isn't a usable allocation.")
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
            st.info("Run a live experiment, or pick saved settings, to see how noise affects the answers.")

    if document:
        with st.expander("Run details and downloads"):
            st.caption("Saved results only appear when the scenario, settings, code and library "
                       "versions all match the run that produced them.")
            st.json({"schema_version": document.get("schema_version"), "config": document["config"],
                     "metadata": document.get("metadata"), "cache_key": document.get("cache_key"),
                     "scenario": document["scenario"]})
            left, right = st.columns(2)
            filename = f"lifelineq_{scenario_name}_lambda{weight:g}_k{k}_p{p}_seed{seed}"
            left.download_button("Download complete JSON", json.dumps(document, indent=2),
                                 file_name=f"{filename}.json", mime="application/json", width="stretch")
            right.download_button("Download metrics CSV", pd.DataFrame(results_rows(document)).to_csv(index=False),
                                  file_name=f"{filename}.csv", mime="text/csv", width="stretch")
    st.markdown('<p class="lq-foot">Built by Alexander Jacob and Shravan Suresh for Qompute 2026. '
                'A research prototype to start a conversation, not a tool for real emergency '
                'decisions.</p>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
