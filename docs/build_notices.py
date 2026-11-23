"""Collect license and notice files for the installed runtime and build dependencies."""

from importlib import metadata
import json
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def python_roots(path):
    for original in path.read_text(encoding="utf-8").splitlines():
        line = original.partition("#")[0].strip()
        if line.startswith("-r "):
            yield from python_roots(path.parent / line[3:])
        elif line:
            yield Requirement(line)


def python_notices():
    pending = list(python_roots(ROOT / "requirements-engine.txt"))
    scanned = set()
    results = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate():
            continue
        dist = metadata.distribution(requirement.name)
        identity = (dist.metadata["Name"], tuple(sorted(requirement.extras)))
        if identity in scanned:
            continue
        scanned.add(identity)
        results[identity[0]] = dist
        for entry in dist.requires or ():
            dependency = Requirement(entry)
            if not dependency.marker or any(dependency.marker.evaluate({"extra": extra})
                                            for extra in {"", *requirement.extras}):
                dependency.marker = None
                pending.append(dependency)
    for name, dist in sorted(results.items(), key=lambda item: item[0].lower()):
        yield f"{name} {dist.version}", [
            dist.locate_file(item) for item in (dist.files or ())
            if item.name.casefold().startswith(("licen", "copying", "notice", "copyright"))
            and any(parent.endswith(".dist-info") for parent in item.parts)
        ]


def npm_notices():
    frontend = ROOT / "frontend"
    packages = json.loads((frontend / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    for location, package in sorted(packages.items()):
        folder = frontend / location
        if location and folder.is_dir():
            yield f"{location.removeprefix('node_modules/')} {package['version']}", [
                item for item in sorted(folder.iterdir()) if item.is_file()
                and item.name.casefold().startswith(("licen", "copying", "notice", "copyright"))
            ]


def main():
    target = ROOT / "docs" / "THIRD_PARTY_NOTICES.txt"
    with target.open("w", encoding="utf-8") as output:
        output.write("ATES V2 third-party notices\n")
        output.write("Collected from the installed Windows runtime and frontend build.\n")
        output.write("Other platforms can rebuild this inventory from their installed artifacts.\n")
        for name, files in (*python_notices(), *npm_notices()):
            output.write(f"\n{'=' * 68}\n{name}\n")
            if not files:
                output.write("See the license declaration in the installed package metadata.\n")
            for path in files:
                output.write(f"\n{path.name}\n{path.read_text(encoding='utf-8', errors='replace').strip()}\n")
    print(target)


if __name__ == "__main__":
    main()

