from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.generator import generate_portfolio

p = argparse.ArgumentParser()
p.add_argument("--size", type=int, choices=[100, 500, 1000], default=100)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--out", type=Path, default=Path("../sample-data/synthetic-100.json"))
a = p.parse_args()
portfolio = generate_portfolio(a.size, a.seed)
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(
    json.dumps(portfolio.model_dump(mode="json"), indent=2), encoding="utf-8"
)
print(
    f"wrote {a.out} (synthetic={portfolio.synthetic}, apps={len(portfolio.applications)})"
)
