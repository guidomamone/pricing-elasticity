import csv, glob
seen, rows = set(), []
for fn in sorted(glob.glob("ratings_part*.csv")):
    with open(fn, newline="", encoding="utf-8") as f:
        n = 0
        for r in csv.DictReader(f):
            n += 1
            if r["const"] and r["const"] not in seen:
                seen.add(r["const"])
                rows.append(r)
        print(f"{fn}: {n} rows read")
with open("ratings_final.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["const", "title", "your_rating", "date_rated", "raw_text"])
    w.writeheader()
    w.writerows(rows)
print(f"ratings_final.csv: {len(rows)} unique titles")
