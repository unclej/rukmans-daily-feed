import os
import subprocess
import json
from datetime import date, datetime
from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv(os.path.expanduser(".env"))

GITHUB_USERNAME = os.getenv("GH_USERNAME")
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
PAGES_URL = f"https://{GITHUB_USERNAME}.github.io/rukmans-daily-feed"
SOURCE_ARTWORK = os.path.join(os.path.dirname(__file__), "jrukman-meatpie.jpg")
ARTWORK_FILENAME = "artwork.jpg"
ARTWORK_SIZE = 3000


def ensure_artwork():
    """Center-crop and resize source artwork to a square, copy to repo if not present."""
    dest = os.path.join(REPO_PATH, ARTWORK_FILENAME)
    if os.path.exists(dest):
        return
    img = Image.open(SOURCE_ARTWORK)
    img = ImageOps.exif_transpose(img)  # apply EXIF rotation before anything else
    img = img.rotate(-90, expand=True)  # 90 degrees clockwise
    img = img.convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((ARTWORK_SIZE, ARTWORK_SIZE), Image.LANCZOS)
    img.save(dest, "JPEG", quality=95)
    print(f"✓ Artwork written ({ARTWORK_SIZE}x{ARTWORK_SIZE})")


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
    <itunes:image href="{PAGES_URL}/{ARTWORK_FILENAME}"/>
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

    # Ensure podcast artwork is in the repo
    ensure_artwork()

    # Convert WAV to MP3
    mp3_path = convert_to_mp3(audio_path)
    if not mp3_path:
        return False

    # Copy MP3 to repo (skip if already in place)
    filename = os.path.basename(mp3_path)
    dest_path = os.path.join(REPO_PATH, "episodes", filename)
    if os.path.abspath(mp3_path) != os.path.abspath(dest_path):
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

    # Update episodes index — deduplicate by URL, keep last 30
    episodes = load_episodes_index()
    episodes = [e for e in episodes if e["url"] != episode_url]
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


def update_artwork():
    """Refresh artwork and regenerate the feed, without touching episodes or using AI credits."""
    # Remove existing artwork so ensure_artwork() rewrites it from source
    dest = os.path.join(REPO_PATH, ARTWORK_FILENAME)
    if os.path.exists(dest):
        os.remove(dest)

    ensure_artwork()

    episodes = load_episodes_index()
    rss_content = generate_rss(episodes)
    feed_path = os.path.join(REPO_PATH, "feed.xml")
    with open(feed_path, "w") as f:
        f.write(rss_content)
    print(f"✓ Feed regenerated ({len(episodes)} episodes)")

    print("Pushing to GitHub...")
    cmds = [
        ["git", "-C", REPO_PATH, "add", "."],
        ["git", "-C", REPO_PATH, "commit", "-m", "Update podcast artwork and feed"],
        ["git", "-C", REPO_PATH, "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Git error: {result.stderr}")
            return False

    print("✓ Pushed to GitHub")
    print(f"\nFeed URL: {PAGES_URL}/feed.xml")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--artwork":
        update_artwork()
    else:
        audio = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test.wav"
        script = sys.argv[2] if len(sys.argv) > 2 else "/tmp/briefing_script.txt"
        upload_episode(audio, script)
