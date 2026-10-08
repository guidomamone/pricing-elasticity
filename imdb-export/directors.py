import csv, gzip, json, os, sys
from collections import defaultdict

DATA = "imdb_data"
MIN_VOTES = 5000          # a film needs this many IMDb votes to be recommended
MIN_RATING = 6.8          # and at least this IMDb rating
LIKE_THRESHOLD = 7.5      # 2+ films rated: director is "liked" at this adjusted average
EXPLORE_MIN_RATING = 8    # 1 film rated: director goes on the explore list if you gave it this or more
PRIOR_K = 1.0             # pulls few-film directors toward your overall average
REPEAT_PENALTY = 0.3      # spreads results: each extra film by the same director ranks a bit lower
DISC_MIN_FILMS = 3        # new directors need this many well-known films
DISC_MIN_MEAN = 7.2       # and this average IMDb rating across them
GENRE_FIT_WEIGHT = 1.5    # taste-by-genre weight for "directors to discover" only (0 turns it off)

EXCLUDE_INDIAN = True
INDIAN_LANGS = {"hi", "ta", "te", "ml", "kn", "bn", "mr", "gu", "pa", "or", "as", "bho", "sa"}
EXCLUDE_LANGS = INDIAN_LANGS   # use {"hi"} to remove only Hindi (Bollywood); set the same in enrich.py
EXCLUDE_NAMES = set()          # add director names here to hide them, e.g. {"Some Director"}
NULL = "\\N"

csv.field_size_limit(10**9)

def tsv(name):
    f = gzip.open(os.path.join(DATA, name), "rt", encoding="utf-8", newline="")
    reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
    header = next(reader)
    return reader, {h: i for i, h in enumerate(header)}

def fmt_rt(m):
    if not m:
        return "?"
    return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m}m"

# 1. Your ratings
mine = {}
with open("ratings_final.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["const"] and r["your_rating"]:
            mine[r["const"]] = int(r["your_rating"])
print(f"Loaded {len(mine)} of your ratings")

# 2. Movies only (features and TV movies, no adult titles)
print("Reading title.basics ...")
movies = {}
reader, ix = tsv("title.basics.tsv.gz")
t, ti, y, g, a, rt = (ix["titleType"], ix["primaryTitle"], ix["startYear"], ix["genres"],
                      ix["isAdult"], ix["runtimeMinutes"])
for row in reader:
    if row[t] in ("movie", "tvMovie") and row[a] != "1":
        movies[row[0]] = (row[ti], "" if row[y] == NULL else row[y],
                          [] if row[g] == NULL else row[g].split(","),
                          int(row[rt]) if row[rt].isdigit() else 0)

print("Reading title.ratings ...")
imdb = {}
reader, ix = tsv("title.ratings.tsv.gz")
for row in reader:
    if row[0] in movies:
        imdb[row[0]] = (float(row[ix["averageRating"]]), int(row[ix["numVotes"]]))

print("Reading title.crew ...")
dir_films = defaultdict(list)
directors_of = {}
reader, ix = tsv("title.crew.tsv.gz")
d = ix["directors"]
for row in reader:
    if row[0] in movies and row[d] != NULL:
        ds = row[d].split(",")
        directors_of[row[0]] = ds
        for n in ds:
            dir_films[n].append(row[0])

# 3. Flag Indian films and directors (rough first pass, TMDB makes the final call later)
indian_films, indian_dirs = set(), set()
if EXCLUDE_INDIAN:
    print("Reading title.akas (the slow one, a few minutes) ...")
    all_indian = EXCLUDE_LANGS == INDIAN_LANGS
    orig_in, in_lang, western = set(), set(), set()
    reader, ix = tsv("title.akas.tsv.gz")
    tid, reg, lang, orig = ix["titleId"], ix["region"], ix["language"], ix["isOriginalTitle"]
    for row in reader:
        c = row[tid]
        if c not in movies:
            continue
        region, lg = row[reg], row[lang]
        if region in ("US", "GB"):
            western.add(c)
        if row[orig] == "1" and (lg in EXCLUDE_LANGS or (region == "IN" and all_indian)):
            orig_in.add(c)
        elif region == "IN" and lg in EXCLUDE_LANGS:
            in_lang.add(c)
    indian_films = {c for c in movies if c in orig_in or (c in in_lang and c not in western)}
    for dn, films in dir_films.items():
        if sum(1 for c in films if c in indian_films) / len(films) >= 0.4:
            indian_dirs.add(dn)
    print(f"Flagged {len(indian_films)} films and {len(indian_dirs)} directors as Indian")

def skip_dir(dn):
    return dn in indian_dirs

def skip_film(c):
    return c in indian_films

rated_movies = [c for c in mine if c in movies]
if not rated_movies:
    sys.exit("None of your ratings matched a movie. Check ratings_final.csv.")
gmean = sum(mine[c] for c in rated_movies) / len(rated_movies)
print(f"{len(rated_movies)} of your ratings are movies. Your average movie rating: {gmean:.2f}")

# 4. Your taste by genre (used only for "directors to discover")
gsum, gcnt = defaultdict(float), defaultdict(int)
for c in rated_movies:
    for gn in movies[c][2]:
        gsum[gn] += mine[c] - gmean
        gcnt[gn] += 1
aff = {gn: (gsum[gn] / gcnt[gn]) * gcnt[gn] / (gcnt[gn] + 5) for gn in gcnt}

# 5. Score every director you have rated
dscore = {}
for dn, films in dir_films.items():
    rs = [mine[c] for c in films if c in mine]
    if rs:
        dscore[dn] = ((sum(rs) + PRIOR_K * gmean) / (len(rs) + PRIOR_K), len(rs), sum(rs) / len(rs))
removed = {dn for dn in dscore if skip_dir(dn)}
list_a = {dn for dn, v in dscore.items() if v[1] >= 2 and v[0] >= LIKE_THRESHOLD and not skip_dir(dn)}
list_b = {dn for dn, v in dscore.items() if v[1] == 1 and v[2] >= EXPLORE_MIN_RATING and not skip_dir(dn)}

def bonus_a(dn):
    return 0.5 * (dscore[dn][0] - LIKE_THRESHOLD)

def bonus_b(dn):
    return 0.3 * (dscore[dn][2] - EXPLORE_MIN_RATING)

def film_recs(directors, bonus):
    cand = defaultdict(list)   # director -> [(base score, film)]
    for dn in directors:
        for c in dir_films[dn]:
            if c in mine or c not in imdb or skip_film(c):
                continue
            avg, votes = imdb[c]
            if votes < MIN_VOTES or avg < MIN_RATING:
                continue
            cand[dn].append((avg + bonus(dn), c))
    out = {}
    for dn, lst in cand.items():
        lst.sort(reverse=True)
        for k, (base, c) in enumerate(lst):
            score = base - REPEAT_PENALTY * k
            if c not in out or score > out[c][0]:
                out[c] = (score, dn)
    return sorted(out.items(), key=lambda kv: -kv[1][0])

recs_a = film_recs(list_a, bonus_a)
recs_b = film_recs(list_b, bonus_b)

# 6. Directors you have never rated, who look like your taste
disc = []
for dn, films in dir_films.items():
    if dn in dscore or skip_dir(dn):
        continue
    notable = [c for c in films if c in imdb and imdb[c][1] >= MIN_VOTES and not skip_film(c)]
    if len(notable) < DISC_MIN_FILMS:
        continue
    mean_r = sum(imdb[c][0] for c in notable) / len(notable)
    if mean_r < DISC_MIN_MEAN:
        continue
    fits = []
    for c in notable:
        gs = movies[c][2]
        fits.append(sum(aff.get(x, 0) for x in gs) / len(gs) if gs else 0)
    fit = sum(fits) / len(fits)
    notable.sort(key=lambda c: -imdb[c][0])
    disc.append((mean_r + GENRE_FIT_WEIGHT * fit, dn, len(notable), mean_r, fit, notable[:5]))
disc.sort(reverse=True)
disc = disc[:300]

# 7. Unseen animated movies (no genre bonus, only a bonus for directors you like)
anim = []
for c, (title, year, genres, runtime) in movies.items():
    if "Animation" not in genres or c in mine or c not in imdb or skip_film(c):
        continue
    avg, votes = imdb[c]
    if votes < MIN_VOTES or avg < MIN_RATING:
        continue
    ds = directors_of.get(c, [])
    if any(skip_dir(dn) for dn in ds):
        continue
    bonus = max([bonus_a(dn) for dn in ds if dn in list_a] + [bonus_b(dn) for dn in ds if dn in list_b] + [0.0])
    anim.append((avg + bonus, c, ds))
anim.sort(key=lambda x: -x[0])

# 8. Director names
needed = ({dn for _, (_, dn) in recs_a} | {dn for _, (_, dn) in recs_b} | {x[1] for x in disc}
          | removed | {dn for _, _, ds in anim for dn in ds})
print("Reading name.basics ...")
names = {}
reader, ix = tsv("name.basics.tsv.gz")
for row in reader:
    if row[0] in needed:
        names[row[0]] = row[ix["primaryName"]]

def nm(n):
    return names.get(n, n)

# 9. Write results
def write_films(fn, recs):
    n = 0
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["const", "title", "year", "runtime", "imdb_rating", "votes", "genres", "director",
                    "your_films_by_them", "your_average_for_them", "rec_score"])
        for c, (score, dn) in recs:
            if nm(dn) in EXCLUDE_NAMES:
                continue
            w.writerow([c, movies[c][0], movies[c][1], fmt_rt(movies[c][3]), imdb[c][0], imdb[c][1],
                        "/".join(movies[c][2]), nm(dn), dscore[dn][1], f"{dscore[dn][2]:.1f}", f"{score:.2f}"])
            n += 1
    return n

na = write_films("list_a_directors_2plus.csv", recs_a)
nb = write_films("list_b_keep_exploring.csv", recs_b)

nc = 0
with open("list_c_discover.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["director", "well_known_films", "avg_imdb_rating", "taste_fit", "score", "films"])
    for score, dn, n, mean_r, fit, top in disc:
        if nm(dn) in EXCLUDE_NAMES:
            continue
        films = [{"id": c, "title": movies[c][0], "year": movies[c][1], "rt": fmt_rt(movies[c][3]),
                  "rating": imdb[c][0]} for c in top]
        w.writerow([nm(dn), n, f"{mean_r:.2f}", f"{fit:+.2f}", f"{score:.2f}", json.dumps(films)])
        nc += 1

nanim = 0
with open("cand_animation.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["const", "title", "year", "runtime", "imdb_rating", "votes", "genres", "director", "rec_score"])
    for score, c, ds in anim:
        dnames = " & ".join(nm(dn) for dn in ds)
        if any(nm(dn) in EXCLUDE_NAMES for dn in ds):
            continue
        w.writerow([c, movies[c][0], movies[c][1], fmt_rt(movies[c][3]), imdb[c][0], imdb[c][1],
                    "/".join(movies[c][2]), dnames, f"{score:.2f}"])
        nanim += 1

with open("directors_you_like.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["director", "films_you_rated", "your_average", "adjusted_score"])
    for dn, v in sorted(dscore.items(), key=lambda kv: (-kv[1][0], -kv[1][1])):
        w.writerow([nm(dn), v[1], f"{v[2]:.2f}", f"{v[0]:.2f}"])

print(f"\nList A candidates (2+ films rated): {len(list_a)} directors, {na} films")
print(f"List B candidates (1 film rated): {len(list_b)} directors, {nb} films")
print(f"List C candidates (directors to discover): {nc} directors")
print(f"Animated movie candidates: {nanim}")
if removed:
    print(f"\nDirectors you rated that were removed as Indian ({len(removed)}), check this list looks right:")
    print("  " + ", ".join(sorted(nm(dn) for dn in removed)[:40]))
print("\nDone. Next run: python3 enrich.py")
