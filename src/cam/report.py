"""Static, model-free inspection reports."""

from html import escape
from pathlib import Path

from cam.contracts import EvalReport
from cam.data import prepare_output, read_jsonl


def _display(value):
    if isinstance(value, dict) and "denominator" in value:
        formatted = "undefined" if value["value"] is None else f'{100 * value["value"]:.1f}%'
        return f'{formatted} <small>{value["numerator"]} / {value["denominator"]}</small>'
    return escape(str(value))


def write_report(report: EvalReport, out_dir: Path) -> Path:
    prepare_output(out_dir)
    metrics = report.metrics
    proposer_description = ("a deterministic rule system" if report.manifest["model_status"] == "not_run"
                            else f"the recorded proposer ({report.manifest['model_status']})")
    predictions = read_jsonl(report.run_dir / "predictions.jsonl")
    closed = [row for row in predictions if row["track"] == "closed_loop"]
    first_tid = closed[0]["trajectory_id"] if closed else None
    trace = [row for row in closed if row["trajectory_id"] == first_tid]
    rows = []
    for row in trace:
        observation = row["request"]["observation"]
        proposal = row["proposal"]
        action = proposal["action"] if proposal else "invalid output"
        reason = proposal["reason_code"] if proposal else row["parse_error"]
        commit = row.get("commit")
        decision = f'{commit["status"]} · r{commit["before_revision"]} → r{commit["after_revision"]}' if commit else "No commit"
        rows.append(f'''<tr><td><span class="badge">{escape(action)}</span><p>{escape(reason or '')}</p></td>
        <td><strong>{escape(str(observation['value']))}</strong><p>Effective {escape(str(observation['effective_at']))}<br>Observed {escape(observation['observed_at'])}</p></td>
        <td><details><summary>{escape(observation['source_id'])}</summary><blockquote>{escape(observation['text'])}</blockquote><p>Span [{observation['evidence_start']}, {observation['evidence_end']}) · {escape(observation['authority'])}</p></details><p>{escape(decision)}</p></td></tr>''')
    metric_rows = "".join(f'<tr><th>{escape(name.replace("_", " "))}</th><td>{_display(metrics[name])}</td></tr>' for name in (
        "state_exact_match", "stale_active_rate", "missing_state_rate", "false_overwrite_rate", "provenance_precision", "provenance_recall", "invalid_output_rate", "parse_invalid_rate_gold_history", "parse_invalid_rate_closed_loop", "validator_rejection_rate_gold_history", "validator_rejection_rate_closed_loop", "deterministic_qa_exact_match"))
    classes = "".join(f'<tr><td>{escape(action)}</td><td>{data["support"]}</td><td>{data["precision"]:.3f}</td><td>{data["recall"]:.3f}</td><td>{data["f1"]:.3f}</td></tr>' for action, data in metrics["action_classes"].items())
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Correction-aware memory · offline experiment</title><style>
    :root{{color-scheme:light;--ink:#162b36;--muted:#52636c;--accent:#076b60;--line:#d7e2df}}*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f2;color:var(--ink);font:16px/1.6 system-ui,sans-serif}}main{{max-width:1160px;margin:auto;padding:52px 30px}}h1{{font-size:clamp(30px,5vw,52px);line-height:1.08;letter-spacing:-.04em;margin:16px 0}}h2{{margin-top:0;letter-spacing:-.02em}}.eyebrow{{text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-size:12px;font-weight:700}}.intro{{max-width:760px;color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:30px 0}}.card,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:22px}}.card b{{display:block;font-size:30px;color:var(--accent)}}.card span,small{{display:block;color:var(--muted);font-size:13px}}section{{margin:18px 0;overflow:auto}}table{{width:100%;border-collapse:collapse;text-align:left}}th,td{{padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-weight:600}}td p{{font-size:13px;color:var(--muted);margin:6px 0;overflow-wrap:anywhere}}.badge{{display:inline-block;background:#e6f3ee;color:var(--accent);padding:3px 10px;border-radius:20px;font-weight:650;font-size:13px}}.notice{{border-left:4px solid #b27c2d;padding:12px 18px;background:#fff8e9}}blockquote{{margin:12px 0;font-size:14px;overflow-wrap:anywhere}}details{{max-width:460px}}footer{{color:var(--muted);font-size:13px;overflow-wrap:anywhere}}@media(max-width:650px){{main{{padding:24px 14px}}.cards{{grid-template-columns:repeat(2,1fr)}}section{{padding:14px}}}}
    </style><main><div class="eyebrow">Reproducible engineering experiment · offline milestone</div>
    <h1>Memory that preserves<br>what changed, and when.</h1>
    <p class="intro">An immutable record of facts, stale reports, and authorized corrections. These results measure {escape(proposer_description)} on original synthetic, annotated inputs.</p>
    <div class="cards"><div class="card"><b>{metrics['trajectory_count']}</b><span>synthetic trajectories</span></div><div class="card"><b>{metrics['observation_count']}</b><span>observations, each scored in two tracks</span></div><div class="card"><b>{metrics['action_macro_f1']:.3f}</b><span>fixed-five-action macro-F1</span></div><div class="card"><b>{metrics['invariant_violations']}</b><span>recorded invariant violations</span></div></div>
    <p class="notice">Label review: <strong>{escape(report.manifest['review_status'])}</strong>. Model: {escape(report.manifest['model_status'])}. Adapter: {escape(report.manifest['adapter_status'])}. A perfect rule result on annotated inputs does not demonstrate learned-model superiority.</p>
    <section><h2>State reliability</h2><p>Rates retain their numerators and denominators. Missing state is reported alongside stale state.</p><table>{metric_rows}</table></section>
    <section><h2>One trajectory, step by step</h2><p>{escape(first_tid or '')} · Open a source to inspect its exact evidence. Both effective time and observed time are retained.</p><table><thead><tr><th>Decision</th><th>Claim and time</th><th>Evidence and transaction</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
    <section><h2>Raw action decisions</h2><p>Measured on identical gold-history snapshots. Accumulated state errors are measured separately through closed-loop replay.</p><table><thead><tr><th>Action</th><th>Support</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>{classes}</tbody></table></section>
    <section><h2>Interpretation and limits</h2><p>Candidate values, effective dates, and authority are supplied annotations. This experiment tests bounded memory updates, not arbitrary information extraction. Human label review, real model comparisons, adapter training, external validation, and generalization claims remain separate milestones.</p><p>The two passes preserve different questions: can the proposer choose the right operation, and does its own accumulated memory remain correct?</p></section>
    <footer>Dataset {escape(report.manifest['dataset']['dataset_id'])}<br>Code {escape(str(report.manifest['git_commit']))} · dirty working tree: {report.manifest['git_dirty']}<br>Environment {escape(report.manifest['platform'])} · Python {escape(report.manifest['python'])}<br>Raw predictions, checkpoints, per-trajectory scores, SQLite ledger, configuration and provenance are saved beside this report.</footer></main></html>'''
    path = out_dir / "index.html"
    path.write_text(html)
    return path
