from __future__ import annotations

import html
import json
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    metrics_path = Path(argv[0]) if argv else Path("docs/ab-test-results.json")
    out_path = Path(argv[1]) if len(argv) > 1 else Path("outputs/ccts-performance.html")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in metrics["cases"]:
        saving = float(case["saving_ratio"])
        recall = float(case["anchor_recall"])
        gate = "PASS" if recall >= 1.0 and saving >= 0.25 else "CHECK"
        rows.append(
            "<tr>"
            f"<td>{html.escape(case['name'])}</td>"
            f"<td>{html.escape(case['type'])}</td>"
            f"<td>{case['baseline_tokens']}</td>"
            f"<td>{case['optimized_tokens']}</td>"
            f"<td>{saving:.1%}</td>"
            f"<td>{recall:.0%}</td>"
            f"<td><span class='{gate.lower()}'>{gate}</span></td>"
            "</tr>"
        )
    body = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CCTS Performance</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, system-ui, sans-serif; background: #eef3f7; color: #17212b; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 18px 48px; }}
    section {{ background: white; border: 1px solid #d8e2eb; border-radius: 8px; padding: 22px; box-shadow: 0 14px 36px rgba(24,38,52,.12); }}
    h1 {{ margin: 0 0 12px; font-size: clamp(28px, 4vw, 44px); }}
    .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }}
    .stat {{ border: 1px solid #d8e2eb; border-radius: 8px; padding: 14px; background: #f6f9fb; }}
    .stat strong {{ display: block; font-size: 25px; color: #127a57; }}
    .stat span {{ color: #5c6d7c; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid #d8e2eb; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 11px; border-bottom: 1px solid #d8e2eb; text-align: left; font-size: 14px; }}
    th {{ background: #edf4fa; font-size: 12px; text-transform: uppercase; }}
    .pass {{ color: #127a57; font-weight: 800; }}
    .check {{ color: #a26600; font-weight: 800; }}
    @media (max-width: 760px) {{
      .stats {{ grid-template-columns: 1fr; }}
      table, thead, tbody, tr, td {{ display: block; width: 100%; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid #d8e2eb; padding: 8px 0; }}
      td {{ border-bottom: 0; }}
    }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>CCTS 성능 평가표</h1>
    <p>CCTS는 기존 raw Codex 컨텍스트 대신 compact preview + SQLite raw vault + ctx://capture 참조를 사용합니다.</p>
    <div class="stats">
      <div class="stat"><strong>{metrics['overall_baseline_tokens']}</strong><span>baseline tokens</span></div>
      <div class="stat"><strong>{metrics['overall_optimized_tokens']}</strong><span>optimized tokens</span></div>
      <div class="stat"><strong>{metrics['overall_saving_ratio']:.1%}</strong><span>overall saving</span></div>
      <div class="stat"><strong>{metrics['anchor_recall']:.0%}</strong><span>anchor recall</span></div>
    </div>
    <table>
      <thead><tr><th>Case</th><th>Type</th><th>Raw</th><th>CCTS</th><th>Saving</th><th>Recall</th><th>Gate</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
