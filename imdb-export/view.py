import csv, os, sys

page = int(sys.argv[1]) if len(sys.argv) > 1 else 1
P = os.environ.get("VIEW_PREFIX", "")
N = 20

def short_dir(s):
    parts = [p.strip() for p in s.split(" & ")]
    return " & ".join(parts[:2]) + (f" y {len(parts) - 2} mas" if len(parts) > 2 else "")

def load(fn):
    with open(fn, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[(page - 1) * N: page * N], len(rows)

def header(title, rows, total):
    first = (page - 1) * N + 1 if rows else 0
    print(f"\n=== {title} (showing {first}-{(page - 1) * N + len(rows)} of {total}) ===\n")

def show_directors_films(title, fn):
    rows, total = load(fn)
    header(title, rows, total)
    for r in rows:
        print(f"{r['imdb_rating']}  {r['title']} ({r['year']}, {r['runtime']})  -  {short_dir(r['director'])}  "
              f"(you rated {r['your_films_by_them']} of theirs, avg {r['your_average_for_them']})  ->  {r['where']}")

def show_plain_films(title, fn):
    rows, total = load(fn)
    header(title, rows, total)
    for r in rows:
        print(f"{r['imdb_rating']}  {r['title']} ({r['year']}, {r['runtime']})  -  {short_dir(r['director'])}  ->  {r['where']}")

show_directors_films("DIRECTORS YOU WATCHED 2+ MOVIES OF", P + "final_a.csv")
show_directors_films("KEEP EXPLORING (1 MOVIE WATCHED, YOU LIKED IT)", P + "final_b.csv")

rows, total = load(P + "final_c.csv")
header("DIRECTORS TO DISCOVER", rows, total)
for r in rows:
    print(f"{short_dir(r['director'])}  -  start with: {r['start_with']}")

show_plain_films("ANIMATED MOVIES (NOT ANIME)", P + "final_anim.csv")
show_plain_films("ANIME MOVIES", P + "final_anime.csv")

print("\nStreaming data: JustWatch, via TMDB. Only titles on your services are shown.")
print(f"For the next 20 of each list run: python3 view.py {page + 1}")
