"""UTF-8 CSV serialization for downloads."""

import csv
from io import StringIO


def csv_text(rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    for row in rows:
        writer.writerow([
            "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
            for value in row
        ])
    return stream.getvalue()

