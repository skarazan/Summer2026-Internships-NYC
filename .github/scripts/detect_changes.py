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

def is_nyc_or_remote(locations):
    for loc in locations:
        l = loc.lower()
        if any(kw in l for kw in ('new york', 'nyc', 'manhattan', 'brooklyn')):
            return True
        if 'remote' in l:
            return True
    return False

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

added = [e for e in new if e['id'] in (new_ids - old_ids) and is_nyc_or_remote(e.get('locations', []))]
reactivated = [
    e for e in new
    if e['id'] in old_ids
    and e.get('active') and not old_by_id[e['id']].get('active')
    and is_nyc_or_remote(e.get('locations', []))
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
    lines = []
    for e in added[:20]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🆕 **{e['company_name']}** — {e['title']}\n📍 {locs}\n🔗 <{url}>")
    for e in reactivated[:10]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🔓 **{e['company_name']}** — {e['title']} (reopened)\n📍 {locs}\n🔗 <{url}>")
    if len(added) > 20:
        lines.append(f"...and {len(added) - 20} more new listings")
    message = "@everyone\n\n" + "\n\n".join(lines)
    with open(".github/scripts/discord_message.txt", "w") as f:
        f.write(message)
    with open(output_file, "a") as f:
        f.write("has_new_listings=true\n")
else:
    with open(output_file, "a") as f:
        f.write("has_new_listings=false\n")
    print("No new listings.")
