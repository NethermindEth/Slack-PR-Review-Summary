import os
import sys
import requests
from datetime import datetime, timedelta
from collections import Counter

# --- Config ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO = os.getenv("REPO") or "org/repo-name"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# --- Input parameter ---
# Default = 7 days (if not passed as GitHub Action input)
try:
    days = int(sys.argv[1])
except (IndexError, ValueError):
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


def format_slack_message(counts, days):
    """Create Slack-friendly message text."""
    if not counts:
        return f"*No PR reviews found in the last {days} days.*"

    lines = [f"*PR Reviews in the last {days} days* 📊\n"]
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
    message = format_slack_message(counts, days)
    post_to_slack(message)
    print("✅ Report sent to Slack")
