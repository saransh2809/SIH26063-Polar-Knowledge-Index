"""Walk through unverified test questions and record a human verdict for each.

For an answerable row, open the page link, find the expected fact on the scan, then answer:
  y = verified   n = wrong (row is marked rejected)   e = edit the fact   s = skip   q = quit

    .venv\\Scripts\\python -m eval.verify --name "Your Name"
"""
import argparse

from eval.common import load, save

FRONTEND = "http://localhost:3000"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="your name, recorded as verified_by")
    args = ap.parse_args()
    rows = load()
    todo = [r for r in rows if r["status"] == "unverified"]
    print(f"{len(todo)} rows to verify.\n")
    for r in todo:
        print("=" * 80)
        print(f"#{r['id']}  {r['question']}")
        if r["answerable"] == "yes":
            print(f"Expected fact: “{r['expected_fact']}”")
            print(f"Check on page: {FRONTEND}/page/{r['expected_item_id']}/{r['expected_page']}")
        else:
            print("Expected: the system should REFUSE. Confirm the archive does not answer this.")
        choice = input("[y]es verified / [n]o / [e]dit fact / [s]kip / [q]uit: ").strip().lower()
        if choice == "q":
            break
        if choice == "e" and r["answerable"] == "yes":
            r["expected_fact"] = input("Exact phrase as printed on the page: ").strip()
            choice = "y"
        if choice == "y":
            r["status"], r["verified_by"] = "verified", args.name
        elif choice == "n":
            r["status"], r["verified_by"] = "rejected", args.name
        save(rows)
    done = sum(1 for r in rows if r["status"] == "verified")
    print(f"\nVerified rows: {done}. Saved to eval/questions.csv")


if __name__ == "__main__":
    main()
