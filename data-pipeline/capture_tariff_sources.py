"""Archive public tariff pages and extract their tables for a manual rate review.

Fetching a page is evidence capture, never automatic tariff approval. No keys,
cookies or account-specific pages are used by this script.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.request import Request, urlopen


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []
        elif tag in {"br", "p", "div"} and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def capture(url: str, output: Path):
    at = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    try:
        with urlopen(Request(url, headers={"User-Agent": "ParkChoiceSG-student-tariff-review/1.0"}),
                     timeout=30) as response:
            raw = response.read()
            final_url = response.url
        parser = Tables()
        parser.feed(raw.decode("utf-8", errors="replace"))
        filename = digest + ".html.gz"
        (output / filename).write_bytes(gzip.compress(raw))
        return {"url": url, "final_url": final_url, "retrieved_at": at,
                "file": filename, "sha256": hashlib.sha256(raw).hexdigest(),
                "status": "captured", "tables": parser.rows}
    except Exception as exc:
        return {"url": url, "retrieved_at": at, "status": "failed",
                "error_type": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "manifest.json").exists():
        parser.error("choose a new capture directory; existing evidence is immutable")
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda u: capture(u, args.output), args.urls))
    (args.output / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(json.dumps({"captured": sum(r["status"] == "captured" for r in records),
                      "failed": [r["url"] for r in records if r["status"] != "captured"]}))


if __name__ == "__main__":
    main()
