import os
import subprocess
import json
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser(".env"))

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
REPO_PATH = os.path.expanduser(os.getenv("GITHUB_REPO_PATH"))
PAGES_URL = f"https://{GITHUB_USERNAME}.github.io/rukmans-daily-feed"


def convert_to_mp3(wav_path):
    mp3_path = wav_path.replace(".wav", ".mp3")
    print("Converting to MP3...")
    result = subprocess.run(
        ["ffmpeg", "-i", wav_path, "-codec:a", "libmp3lame",
         "-qscale:a", "4", "-y", mp3_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}")
        return None
    size_mb = os.path.getsize(mp3_path) / 1024 / 1024
    print(f"✓ MP3 created ({size_mb:.1f} MB)")
    return mp3_path


def generate_rss(episodes):
    items = ""
    for ep in episodes:
        items += f"""
    <item>
      <title>{ep['title']}</title>
      <description>{ep['description']}</description>
      <enclosure url="{ep['url']}" length="{ep['size']}" type="audio/mpeg"/>
      <pubDate>{ep['pubdate']}</pubDate>
      <guid>{ep['url']}</guid>
    </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Morning Briefing</title>
    <description>Your daily AI-generated newsletter briefing</description>
    <link>{PAGES_URL}</link>
    <language>en-us</language>
    <itunes:author>{GITHUB_USERNAME}</itunes:author>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>{items}
  </channel>
</rss>"""


def load_episodes_index():
    index_path = os.path.join(REPO_PATH, "episodes.json")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return json.load(f)
    return []


def save_episodes_index(episodes):
    index_path = os.path.join(REPO_PATH, "episodes.json")
    with open(index_path, "w") as f:
        json.dump(episodes, f, indent=2)


def upload_episode(audio_path, script_path):
    today = date.today().strftime("%Y-%m-%d")
    title = f"Morning Briefing — {date.today().strftime('%B %d, %Y')}"

    # Convert WAV to MP3
    mp3_path = convert_to_mp3(audio_path)
    if not mp3_path:
        return False

    # Copy MP3 to repo
    filename = os.path.basename(mp3_path)
    dest_path = os.path.join(REPO_PATH, "episodes", filename)
    subprocess.run(["cp", mp3_path, dest_path])

    # Read script for description
    with open(script_path, "r") as f:
        description = f.read()[:300].replace("<", "&lt;").replace(">", "&gt;")

    # Get file size
    size = os.path.getsize(dest_path)

    # Build episode entry
    episode_url = f"{PAGES_URL}/episodes/{filename}"
    pubdate = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    new_episode = {
        "title": title,
        "description": description,
        "url": episode_url,
        "size": size,
        "pubdate": pubdate,
        "date": today,
    }

    # Update episodes index — keep last 30
    episodes = load_episodes_index()
    episodes.insert(0, new_episode)
    episodes = episodes[:30]
    save_episodes_index(episodes)

    # Regenerate RSS feed
    rss_content = generate_rss(episodes)
    feed_path = os.path.join(REPO_PATH, "feed.xml")
    with open(feed_path, "w") as f:
        f.write(rss_content)

    print(f"✓ RSS feed updated with {len(episodes)} episodes")

    # Git commit and push
    print("Pushing to GitHub...")
    cmds = [
        ["git", "-C", REPO_PATH, "add", "."],
        ["git", "-C", REPO_PATH, "commit", "-m",
         f"Morning briefing {today}"],
        ["git", "-C", REPO_PATH, "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Git error: {result.stderr}")
            return False

    print("✓ Pushed to GitHub")
    print(f"\nFeed URL: {PAGES_URL}/feed.xml")
    print("Add this URL to Apple Podcasts on your iPhone")
    return True


if __name__ == "__main__":
    import sys
    audio = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test.wav"
    script = sys.argv[2] if len(sys.argv) > 2 else "/tmp/briefing_script.txt"
    upload_episode(audio, script)
