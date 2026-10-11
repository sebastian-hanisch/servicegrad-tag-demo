"""Standardfehler-Schätzer der Simulation gegen die Streuung über Zufalls-Seeds (AP 0 d).

Aufruf (Python mit vollem Pfad): python tools/se_check.py [--instances 50] [--seeds 12] [--days 14] [--out <Pfad>/se_check.json]

Je Instanz (Basiszelle, reihum über die fünf Profile) und Plan (Z und O): `--seeds` Simulationen mit verschiedenen Zufalls-Seeds. Die
Standardabweichung der Tages-Servicegrade über die Seeds ist der Maßstab; verglichen wird der mittlere Standardfehler aus den Tagesmitteln
(`sgt_sim.mean_and_se`, ein Lauf), einmal mit Tagesblöcken der Länge 1 (Vorgabe) und der Länge 2. Ein Verhältnis um 1 heißt: der Schätzer
trifft die Streuung im Mittel. Einzelne Instanzen streuen stark (zwölf Seeds schätzen die Standardabweichung auf etwa ± 20 %).
"""

import argparse
import json
import pathlib
import statistics as st
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_constants as C  # noqa: E402
import sgt_pipeline as PL  # noqa: E402
import sgt_sim as S  # noqa: E402
from sgt_rng import seed_from  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", type=int, default=50)
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    rows = []
    for k in range(args.instances):
        profile = C.PROFILE_ORDER[k % len(C.PROFILE_ORDER)]
        seed = k // len(C.PROFILE_ORDER)
        s = PL.Settings(profile=profile, seed=seed)
        prob, plans, _ = PL.stage1(s)
        o, _ = PL.stage2(s, prob, plans)
        plans["O"] = o
        for key in ("Z", "O"):
            sls, se1, se2 = [], [], []
            for r in range(args.seeds):
                res = S.simulate(prob, plans[key].n, days=args.days, warm=C.SIM_WARM_DAYS, seed=seed_from("se", profile, seed, key, r))
                m, a = S.mean_and_se(res, 1)
                sls.append(m)
                se1.append(a)
                se2.append(S.mean_and_se(res, 2)[1])
            rows.append({"profile": profile, "seed": seed, "plan": key, "sd": 100 * st.stdev(sls), "se1": 100 * st.mean(se1), "se2": 100 * st.mean(se2)})
    for label, field in (("Tagesmittel (Blocklänge 1)", "se1"), ("Zweitagesblöcke", "se2")):
        ratios = [r[field] / r["sd"] for r in rows]
        print(f"{label}: mittleres Verhältnis SE / SD {st.mean(ratios):.2f}, Median {st.median(ratios):.2f}, "
              f"10. bis 90. Perzentil {sorted(ratios)[int(0.1 * len(ratios))]:.2f} bis {sorted(ratios)[int(0.9 * len(ratios))]:.2f}, n = {len(rows)}")
    mean_sd = st.mean(r["sd"] for r in rows)
    print(f"mittlere SD über {args.seeds} Zufalls-Seeds bei {args.days} Tagen: {mean_sd:.2f} Punkte, Spanne {min(r['sd'] for r in rows):.2f} bis {max(r['sd'] for r in rows):.2f}")
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
