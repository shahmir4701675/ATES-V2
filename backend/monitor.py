"""Record TLS availability checks during the institution's local working hours."""

import argparse
from calendar import monthrange
from datetime import datetime, time, timedelta
import json
from pathlib import Path
import ssl
from time import monotonic, sleep
from urllib.parse import urlsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo

LOCAL_ZONE = ZoneInfo("Asia/Karachi")
FIRST_MINUTE = time(8)
END_MINUTE = time(18)


def parse_days(value):
    days = {int(day) for day in value.split(",")}
    if not days or days - set(range(1, 8)):
        raise argparse.ArgumentTypeError("Choose weekday numbers from 1 to 7.")
    return days


def sample(url, output, days, context):
    if urlsplit(url).scheme != "https":
        raise ValueError("Monitor the application's HTTPS endpoint.")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            now = datetime.now(LOCAL_ZONE)
            sample_start = monotonic()
            if now.isoweekday() in days and FIRST_MINUTE <= now.time() < END_MINUTE:
                up = False
                try:
                    with urlopen(url, timeout=5, context=context) as response:
                        up = response.status == 200 and b'id="root"' in response.read(65536)
                except OSError:
                    pass
                elapsed = monotonic() - sample_start
                with output.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"at": now.isoformat(timespec="seconds"), "up": up,
                                             "seconds": round(elapsed, 3)}) + "\n")
            current = datetime.now(LOCAL_ZONE)
            sleep(max(.05, 60 - current.second - current.microsecond / 1_000_000))
    except KeyboardInterrupt:
        return


def summarize(path, month, days):
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=LOCAL_ZONE)
    date_count = monthrange(start.year, start.month)[1]
    required = {
        (start + timedelta(days=day, hours=8, minutes=minute)).isoformat(timespec="minutes")
        for day in range(date_count) if (start + timedelta(days=day)).isoweekday() in days
        for minute in range(600)
    }
    samples = {}
    if path.is_file():
        with path.open(encoding="utf-8") as records:
            for line in records:
                observation = json.loads(line)
                key = datetime.fromisoformat(observation["at"]).astimezone(LOCAL_ZONE).isoformat(timespec="minutes")
                if key in required:
                    samples[key] = samples.get(key, True) and bool(observation["up"])
    received = len(samples)
    passing = sum(samples.values())
    return {"month": month, "expected_minutes": len(required), "observed_minutes": received,
            "up_minutes": passing, "missing_minutes": len(required) - received,
            "complete": received == len(required),
            "availability_percent": round(100 * passing / len(required), 3) if received == len(required) else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path(".ates/availability.jsonl"))
    parser.add_argument("--workdays", type=parse_days, default={1, 2, 3, 4, 5})
    commands = parser.add_subparsers(dest="action", required=True)
    probe = commands.add_parser("probe")
    probe.add_argument("url")
    probe.add_argument("--ca-file")
    report = commands.add_parser("report")
    report.add_argument("month")
    args = parser.parse_args()
    if args.action == "probe":
        sample(args.url, args.log, args.workdays, ssl.create_default_context(cafile=args.ca_file))
    else:
        print(json.dumps(summarize(args.log, args.month, args.workdays), indent=2))


if __name__ == "__main__":
    main()

