import csv, json, os, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = os.environ.get("TMDB_KEY", "").strip()
if not KEY:
    sys.exit("Falta la clave de TMDB. Corre primero el comando que empieza con: read -s")
BASE = os.environ.get("TMDB_BASE", "https://api.themoviedb.org/3")
COUNTRIES = ("AR", "US")   # countries we fetch data for (keep both so you can switch back any time)
SHOW_COUNTRIES = ("US",)   # countries shown in the lists; use ("AR", "US") for both
DISABLED_SERVICES = {"Tubi"}   # services to ignore for now; use set() to bring Tubi back
STREAM_KEYS = ("flatrate", "free", "ads")   # streaming = subscription, free or with ads (not rent or buy)
INDIAN_LANGS = {"hi", "ta", "te", "ml", "kn", "bn", "mr", "gu", "pa", "or", "as", "bho", "sa"}
EXCLUDE_LANGS = INDIAN_LANGS   # must match directors.py, e.g. {"hi"} for Hindi only
CACHE = "tmdb_cache.json"
MIN_RUNTIME = 60   # minutes; also drops most TV specials

# Only these services count. Names TMDB uses are matched by prefix; "Amazon Channel" style add-ons are ignored.
SERVICES = [
    ("Paramount+", ("paramount plus", "paramount+")),
    ("Peacock", ("peacock",)),
    ("Netflix", ("netflix",)),
    ("Disney+", ("disney plus", "disney+")),
    ("Hulu", ("hulu",)),
    ("Prime Video", ("amazon prime video", "prime video")),
    ("Apple TV", ("apple tv",)),
    ("HBO Max", ("hbo max",)),
    ("Crunchyroll", ("crunchyroll",)),
    ("Tubi", ("tubi",)),
]

# Temporary overrides (they do not change your usual setup):
#   ENRICH_ONLY=Netflix        keep only that service
#   ENRICH_COUNTRIES=AR,US     countries to show (default: SHOW_COUNTRIES above)
#   ENRICH_PREFIX=netflix_     write netflix_final_*.csv instead of final_*.csv
ONLY = os.environ.get("ENRICH_ONLY", "").strip()
if ONLY:
    SERVICES = [s for s in SERVICES if s[0].lower() == ONLY.lower()]
    if not SERVICES:
        sys.exit(f"No conozco el servicio {ONLY!r}. Opciones: Paramount+, Peacock, Netflix, Disney+, Hulu, Prime Video, Apple TV, HBO Max, Crunchyroll, Tubi")
    DISABLED_SERVICES = set()
if os.environ.get("ENRICH_COUNTRIES", "").strip():
    SHOW_COUNTRIES = tuple(x.strip().upper() for x in os.environ["ENRICH_COUNTRIES"].split(","))
    if not set(SHOW_COUNTRIES) <= set(COUNTRIES):
        sys.exit(f"Paises validos: {', '.join(COUNTRIES)}")
PREFIX = os.environ.get("ENRICH_PREFIX", "")
ALLOWED = {s[0] for s in SERVICES}

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

csv.field_size_limit(10**9)

def api(path, params=None):
    params = dict(params or {})
    headers = {"accept": "application/json"}
    if KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {KEY}"
    else:
        params["api_key"] = KEY
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After", 2)) + 0.5)
                continue
            if e.code in (401, 403):
                return {"_auth_error": e.code}
            if e.code == 404:
                return None
            time.sleep(1 + attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(1 + attempt)
    return None

test = api("/configuration")
if not test or "_auth_error" in test:
    sys.exit("TMDB no acepto la clave (o no hay conexion). Revisa que pegaste bien la clave.")

def lookup(c):
    f = api(f"/find/{c}", {"external_source": "imdb_id"})
    if f is None or "_auth_error" in f:
        return {"error": True}
    res = f.get("movie_results") or []
    if not res:
        return {"tmdb_id": None, "lang": "", "prov": {}}
    m = res[0]
    p = api(f"/movie/{m['id']}/watch/providers")
    if p is None or "_auth_error" in p:
        return {"error": True}
    out = {}
    for cc in COUNTRIES:
        r = (p.get("results") or {}).get(cc) or {}
        names = []
        for k in STREAM_KEYS:
            for x in r.get(k, []):
                if x["provider_name"] not in names:
                    names.append(x["provider_name"])
        out[cc] = names
    return {"tmdb_id": m["id"], "lang": m.get("original_language", ""), "prov": out}

def read(fn):
    with open(fn, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

lists = {name: read(fn) for name, fn in [("a", "list_a_directors_2plus.csv"), ("b", "list_b_keep_exploring.csv"),
                                         ("anim", "cand_animation.csv"), ("c", "list_c_discover.csv")]}
for r in lists["c"]:
    r["_films"] = json.loads(r["films"])

need = []
for name in ("a", "b", "anim"):
    need += [r["const"] for r in lists[name]]
for r in lists["c"]:
    need += [f["id"] for f in r["_films"]]
need = list(dict.fromkeys(need))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
todo = [c for c in need if c not in cache]
print(f"{len(need)} peliculas a revisar, {len(todo)} nuevas (el resto ya estaba guardado)")

def save():
    with open(CACHE, "w") as f:
        json.dump(cache, f)

errors = 0
try:
    with ThreadPoolExecutor(8) as ex:
        for i, (c, r) in enumerate(zip(todo, ex.map(lookup, todo)), 1):
            if r.get("error"):
                errors += 1
            else:
                cache[c] = r
            if i % 200 == 0:
                save()
                print(f"  {i}/{len(todo)} consultadas")
finally:
    save()
if errors:
    print(f"{errors} consultas fallaron. Corre enrich.py de nuevo para reintentarlas.")

def my_services(names):
    out = []
    for n in names:
        low = n.lower().strip()
        if "channel" in low:
            continue
        label = "HBO Max" if low == "max" else None
        if label is None:
            for lab, prefixes in SERVICES:
                if low.startswith(prefixes):
                    label = lab
                    break
        if label and label in ALLOWED and label not in out and label not in DISABLED_SERVICES:
            out.append(label)
    return out

def minutes(rt):
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", rt or "")
    if not m or not (m.group(1) or m.group(2)):
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

def ok(c):
    r = cache.get(c)
    if not r or not r.get("tmdb_id") or r["lang"] in EXCLUDE_LANGS:
        return False
    return any(my_services(r["prov"].get(cc, [])) for cc in SHOW_COUNTRIES)

def long_enough(rt):
    return minutes(rt) >= MIN_RUNTIME

def where(c):
    r = cache[c]
    parts = []
    for cc in SHOW_COUNTRIES:
        labels = my_services(r["prov"].get(cc, []))
        if labels:
            parts.append(f"{cc}: {', '.join(labels)}")
    return " | ".join(parts)

def write(fn, rows, fields):
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

counts = {}
for name, fn in (("a", PREFIX + "final_a.csv"), ("b", PREFIX + "final_b.csv")):
    rows = [dict(r, where=where(r["const"])) for r in lists[name] if ok(r["const"]) and long_enough(r["runtime"])]
    write(fn, rows, ["title", "year", "runtime", "imdb_rating", "director", "your_films_by_them",
                     "your_average_for_them", "where"])
    counts[name] = (len(lists[name]), len(rows))

anime, western = [], []
for r in lists["anim"]:
    c = r["const"]
    if not ok(c) or not long_enough(r["runtime"]):
        continue
    row = dict(r, where=where(c))
    (anime if cache[c]["lang"] == "ja" else western).append(row)
fields = ["title", "year", "runtime", "imdb_rating", "director", "where"]
write(PREFIX + "final_anim.csv", western, fields)
write(PREFIX + "final_anime.csv", anime, fields)
counts["anim"] = (len(lists["anim"]), len(western))
counts["anime"] = (len(lists["anim"]), len(anime))

rows_c = []
for r in lists["c"]:
    keep = [f for f in r["_films"] if ok(f["id"]) and long_enough(f["rt"])][:3]
    if keep:
        start = "; ".join(f"{f['title']} ({f['year']}, {f['rt']}) {f['rating']} [{where(f['id'])}]" for f in keep)
        rows_c.append({"director": r["director"], "start_with": start})
write(PREFIX + "final_c.csv", rows_c, ["director", "start_with"])
counts["c"] = (len(lists["c"]), len(rows_c))

print("\nResultado (candidatas -> en tus servicios, 60 min o mas):")
labels = {"a": "Lista A (2+ peliculas)", "b": "Lista B (seguir explorando)", "c": "Lista C (directores nuevos)",
          "anim": "Animacion no anime", "anime": "Anime"}
for k in ("a", "b", "c", "anim", "anime"):
    print(f"  {labels[k]}: {counts[k][0]} -> {counts[k][1]}")
print("\nListo. Ahora corre: python3 view.py")
