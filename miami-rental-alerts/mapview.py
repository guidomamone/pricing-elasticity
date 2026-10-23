"""Static map of the day's options: OpenStreetMap tiles stitched together with Pillow,
numbered pins that match the numbers in the Telegram lists.

Pillow is imported lazily so the alerts keep working even if it is missing.
"""
import io
import math
import urllib.request

TILE = 256
USER_AGENT = "miami-rental-alerts/1.0 (https://github.com/guidomamone/pricing-elasticity)"
COLORS = {"tennis": (26, 152, 80), "brickell": (44, 127, 184)}
ATTRIBUTION = "© OpenStreetMap contributors"


def project(lat, lon, zoom):
    """Web Mercator pixel coordinates of a point at the given zoom."""
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * TILE
    return x, y


def group_pins(pins):
    """pins: [(number, lat, lon, kind)]. Units of one building share a coordinate, so they are
    grouped into one pin. Returns ([(lat, lon, kind, [numbers])], count_without_coordinates)."""
    groups, missing = {}, 0
    for number, lat, lon, kind in pins:
        if lat is None or lon is None or not (-85 <= lat <= 85 and -180 <= lon <= 180):
            missing += 1
            continue
        group = groups.setdefault((round(lat, 5), round(lon, 5)), [lat, lon, kind, []])
        group[3].append(number)
    return [tuple(g) for g in groups.values()], missing


def fit_zoom(groups, width, height, pad=60, max_zoom=16, min_zoom=10):
    for zoom in range(max_zoom, min_zoom - 1, -1):
        xs, ys = zip(*(project(g[0], g[1], zoom) for g in groups))
        if max(xs) - min(xs) <= width - 2 * pad and max(ys) - min(ys) <= height - 2 * pad:
            return zoom
    return min_zoom


def fetch_tile(zoom, x, y):
    url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def render_map(pins, width=900, height=650, fetch=fetch_tile):
    """Returns (png_bytes, count_without_coordinates); png_bytes is None if nothing can be drawn."""
    groups, missing = group_pins(pins)
    if not groups:
        return None, missing

    from PIL import Image, ImageDraw, ImageFont

    zoom = fit_zoom(groups, width, height)
    points = [project(g[0], g[1], zoom) for g in groups]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    ox, oy = (min(xs) + max(xs)) / 2 - width / 2, (min(ys) + max(ys)) / 2 - height / 2

    canvas = Image.new("RGB", (width, height), (225, 225, 225))
    n, total, failed = 2 ** zoom, 0, 0
    for tx in range(math.floor(ox / TILE), math.floor((ox + width) / TILE) + 1):
        for ty in range(math.floor(oy / TILE), math.floor((oy + height) / TILE) + 1):
            if not 0 <= ty < n:
                continue
            total += 1
            try:
                tile = Image.open(io.BytesIO(fetch(zoom, tx % n, ty))).convert("RGB")
            except Exception:
                failed += 1
                continue
            canvas.paste(tile, (round(tx * TILE - ox), round(ty * TILE - oy)))
    if total and failed == total:
        raise RuntimeError("no map tiles could be downloaded")

    try:
        font = ImageFont.load_default(size=24)
    except TypeError:  # older Pillow
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for (x, y), group in sorted(zip(points, groups), key=lambda pg: pg[0][1]):
        numbers = group[3]
        label = ",".join(str(n_) for n_ in numbers[:3]) + ("+" if len(numbers) > 3 else "")
        left, top, right, bottom = font.getbbox(label)
        w, h = right - left, bottom - top
        box_w, box_h = max(38, w + 20), 38
        cx, cy = x - ox, y - oy
        draw.rounded_rectangle((cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2),
                               radius=19, fill=COLORS.get(group[2], (90, 90, 90)), outline="white", width=2)
        draw.text((cx - w / 2 - left, cy - h / 2 - top), label, font=font, fill="white")

    left, top, right, bottom = font.getbbox(ATTRIBUTION)
    draw.rectangle((width - (right - left) - 12, height - (bottom - top) - 10, width, height), fill=(255, 255, 255))
    draw.text((width - (right - left) - 6, height - (bottom - top) - 6 - top), ATTRIBUTION, font=font, fill=(60, 60, 60))

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue(), missing
