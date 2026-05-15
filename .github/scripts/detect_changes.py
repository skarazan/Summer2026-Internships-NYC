import json
import os

OLD_PATH = ".github/scripts/listings_old.json"
NEW_PATH = ".github/scripts/listings.json"

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

added = [e for e in new if e['id'] in (new_ids - old_ids)]
reactivated = [
    e for e in new
    if e['id'] in old_ids
    and e.get('active') and not old_by_id[e['id']].get('active')
]

changes = added + reactivated
print(f"New: {len(added)}, Reactivated: {len(reactivated)}")

output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")
if changes:
    lines = []
    for e in added[:20]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🆕 **{e['company_name']}** — {e['title']}\n📍 {locs}\n🔗 {url}")
    for e in reactivated[:10]:
        locs = ", ".join(e.get("locations", []))
        url = e.get("url", "")
        lines.append(f"🔓 **{e['company_name']}** — {e['title']} (reopened)\n📍 {locs}\n🔗 {url}")
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
