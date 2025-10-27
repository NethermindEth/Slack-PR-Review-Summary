import os
import sys
import requests
from datetime import datetime, timedelta
from collections import Counter

# --- Config ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- Input parameters ---
try:
    REPO = sys.argv[1]  # e.g., "my-repo"
except IndexError:
    print("Error: Repository name is required as first argument")
    sys.exit(1)

try:
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
except ValueError:
    days = 7

since = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"


def get_pulls():
    """Fetch all PRs updated since the cutoff date."""
    pulls = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/pulls",
            headers=HEADERS,
            params={
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": 50,
                "page": page,
            },
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break

        for pr in data:
            if pr["updated_at"] > since:
                pulls.append(pr)

        if len(data) < 50:
            break
        page += 1

    return pulls


def get_reviews(pulls):
    """Count approvals per reviewer."""
    counts = Counter()
    for pr in pulls:
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/pulls/{pr['number']}/reviews",
            headers=HEADERS,
        )
        r.raise_for_status()
        for review in r.json():
            if review["state"].lower() == "approved":
                counts[review["user"]["login"]] += 1
    return counts


def format_slack_message(counts, days, repo):
    """Create Slack-friendly message text."""
    if not counts:
        return f"*No PR reviews found in the last {days} days for `{repo}`.*"

    lines = [f"*PR Reviews in the last {days} days for `{repo}`* 📊\n"]
    for user, count in counts.most_common():
        lines.append(f"• `{user}`: {count} reviews")
    return "\n".join(lines)


def post_to_slack(message):
    """Send the formatted message to Slack."""
    payload = {"text": message}
    r = requests.post(SLACK_WEBHOOK_URL, json=payload)
    r.raise_for_status()


if __name__ == "__main__":
    pulls = get_pulls()
    counts = get_reviews(pulls)
    message = format_slack_message(counts, days, REPO)
    post_to_slack(message)
    print("✅ Report sent to Slack")
