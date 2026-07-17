import csv
import io


def read_csv_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def csv_response(rows: list[dict[str, object]], fieldnames: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
