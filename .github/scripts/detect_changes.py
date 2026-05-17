import json
import os
import hashlib
import urllib.request

OLD_PATH = ".github/scripts/listings_old.json"
NEW_PATH = ".github/scripts/listings.json"
NOTIFIED_PATH = ".github/scripts/notified_hashes.json"

SIBLING_HASH_URLS = [
    "https://raw.githubusercontent.com/skarazan/Summer2027-Internships/dev/.github/scripts/notified_hashes.json",
    "https://raw.githubusercontent.com/skarazan/Internships-2026/main/.github/data/notified_hashes.json",
    "https://raw.githubusercontent.com/skarazan/southeast-tech-internships-2026-2027/main/.github/data/notified_hashes.json",
]

def job_hash(entry):
    key = f"{entry.get('company_name','').lower().strip()}|{entry.get('title','').lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def fetch_sibling_hashes():
    hashes = set()
    for url in SIBLING_HASH_URLS:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                hashes.update(json.loads(resp.read()))
        except Exception:
            pass
    return hashes

def is_phd(entry):
    title = (entry.get('title') or '').lower()
    return 'phd' in title or 'ph.d' in title

def is_nyc_or_remote_usa(locations):
    has_nyc = False
    has_remote_usa = False
    for loc in locations:
        l = loc.lower()
        if any(kw in l for kw in ('uk', 'united kingdom', 'london', 'england', 'scotland')):
            continue
        if any(kw in l for kw in ('new york', 'nyc', 'brooklyn')):
            has_nyc = True
        if 'manhattan' in l and 'beach' not in l:
            has_nyc = True
        if 'remote' in l:
            if any(kw in l for kw in ('uk', 'canada', 'united kingdom', 'london', 'india', 'europe')):
                continue
            has_remote_usa = True
    return has_nyc or has_remote_usa

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

old = load(OLD_PATH)
new = load(NEW_PATH)

old_ids = {e['id'] for e in old}
new_ids = {e['id'] for e in new}
old_by_id = {e['id']: e for e in old}

added = [e for e in new if e['id'] in (new_ids - old_ids) and is_nyc_or_remote_usa(e.get('locations', [])) and not is_phd(e)]
reactivated = [
    e for e in new
    if e['id'] in old_ids
    and e.get('active') and not old_by_id[e['id']].get('active')
    and is_nyc_or_remote_usa(e.get('locations', [])) and not is_phd(e)
]

notified = set()
if os.path.exists(NOTIFIED_PATH):
    with open(NOTIFIED_PATH) as f:
        notified = set(json.load(f))
sibling_hashes = fetch_sibling_hashes()
all_known = notified | sibling_hashes

added = [e for e in added if job_hash(e) not in all_known]
reactivated = [e for e in reactivated if job_hash(e) not in all_known]

changes = added + reactivated
print(f"New: {len(added)}, Reactivated: {len(reactivated)} (after dedup)")

output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")
if changes:
    for e in changes:
        notified.add(job_hash(e))
    with open(NOTIFIED_PATH, "w") as f:
        json.dump(sorted(notified), f)
    MAX_SHOW = 5
    lines = []
    for e in added[:MAX_SHOW]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🆕 **{e['company_name']}** — {e['title']}\n📍 {locs}\n🔗 <{url}>")
    for e in reactivated[:max(0, MAX_SHOW - len(added))]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🔓 **{e['company_name']}** — {e['title']} (reopened)\n📍 {locs}\n🔗 <{url}>")
    extra = len(added) + len(reactivated) - len(lines)
    if extra > 0:
        lines.append(f"...and **{extra} more** — check the README")
    message = "@everyone\n\n" + "\n\n".join(lines)
    with open(".github/scripts/discord_message.txt", "w") as f:
        f.write(message)
    with open(output_file, "a") as f:
        f.write("has_new_listings=true\n")
else:
    with open(output_file, "a") as f:
        f.write("has_new_listings=false\n")
    print("No new listings.")
