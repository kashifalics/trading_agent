import argparse

from app.gold_research.exp7 import run


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.gold_research.exp7", description=run.__doc__)
    ap.add_argument("stage", choices=("register", "prereg", "develop", "confirm", "report"))
    ap.add_argument("--draws", type=int, default=None)
    a = ap.parse_args()
    if a.stage == "register":
        run.write_register()
    elif a.stage == "prereg":
        run.prereg()
    elif a.stage == "develop":
        run.develop(draws=a.draws)
    elif a.stage == "confirm":
        run.confirm(draws=a.draws)
    else:
        from app.gold_research.exp7 import report

        report.write_reports()


if __name__ == "__main__":
    main()
