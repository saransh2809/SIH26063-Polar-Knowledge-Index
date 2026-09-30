"""Stage 2 reconnaissance: what does each source allow, and does DSpace speak OAI-PMH?

Run from backend/:  .venv\\Scripts\\python -m ingest.recon
Uses only the standard library so it works before anything else is installed.
"""
import time
import urllib.error
import urllib.request
import urllib.robotparser

USER_AGENT = "NCPOR-Polar-Index-SIH-Prototype/0.1 (student project)"

SITES = {
    "DSpace": "http://14.139.119.23:8080",
    "NCPOR website": "https://ncpor.res.in",
    "NPDC": "https://npdc.ncpor.res.in",
}
OAI_PATHS = ["/oai/request?verb=Identify", "/dspace-oai/request?verb=Identify", "/oai/request"]
DSPACE_PAGES = ["/dspace/index.jsp", "/dspace/community-list", "/jspui/", "/xmlui/"]


def fetch(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # network errors, timeouts
        return None, f"{type(e).__name__}: {e}"
    finally:
        time.sleep(1.0)  # polite: at most one request per second


def main() -> None:
    for name, base in SITES.items():
        print(f"\n=== {name} ({base}) ===")
        status, body = fetch(base + "/robots.txt")
        print(f"robots.txt -> {status}")
        if status == 200:
            print("  " + "\n  ".join(body.strip().splitlines()[:20]))
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.splitlines())
            for path in ["/", "/dspace/", "/oai/request", "/rssfeeds", "/exp_rep/"]:
                print(f"  can_fetch({path!r}) = {rp.can_fetch(USER_AGENT, base + path)}")
        elif status is None:
            print(f"  {body}")

    print("\n=== DSpace OAI-PMH ===")
    for path in OAI_PATHS:
        status, body = fetch(SITES["DSpace"] + path)
        verdict = "OAI-PMH" if "<OAI-PMH" in body else "no OAI response"
        print(f"{path} -> {status} ({verdict})")
        if "<repositoryName>" in body:
            print("  " + body.split("<repositoryName>")[1].split("<")[0])

    print("\n=== DSpace UI pages ===")
    for path in DSPACE_PAGES:
        status, body = fetch(SITES["DSpace"] + path)
        title = body.split("<title>")[1].split("</title>")[0].strip() if "<title>" in body else ""
        print(f"{path} -> {status} {title[:80]}")


if __name__ == "__main__":
    main()
