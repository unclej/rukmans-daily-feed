import os
import sys
import subprocess
from datetime import datetime
from fetch_newsletters import fetch_newsletters
from summarize import summarize
from upload import upload_episode
import json


def already_ran_today(today_str):
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "episodes.json")
    if not os.path.exists(index_path):
        return False
    with open(index_path) as f:
        episodes = json.load(f)
    return any(ep.get("date") == today_str for ep in episodes)


def run():
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    today = timestamp[:10]  # YYYY-MM-DD
    audio_path = os.path.expanduser(f"episodes/episode-{timestamp}.wav")

    # Make sure episodes directory exists
    os.makedirs(os.path.expanduser("episodes"), exist_ok=True)

    print(f"\n{'='*50}")
    print(f"Morning Briefing Pipeline — {timestamp}")
    print(f"{'='*50}\n")

    if already_ran_today(today):
        print(f"Episode for {today} already exists. Skipping.")
        sys.exit(0)

    # Step 1 — Fetch newsletters
    print("Step 1/4 — Fetching newsletters...")
    newsletters = fetch_newsletters()
    if not newsletters:
        print("No newsletters found today. Exiting.")
        sys.exit(0)

    newsletters_path = "/tmp/newsletters.json"
    with open(newsletters_path, "w") as f:
        json.dump(newsletters, f, indent=2, ensure_ascii=False)
    print(f"✓ Fetched {len(newsletters)} newsletters\n")

    # Step 2 — Summarize
    print("Step 2/4 — Summarizing with AI...")
    script_path = summarize(newsletters_path)
    if not script_path:
        print("Summarization failed. Exiting.")
        sys.exit(1)
    print("✓ Script written\n")

    # Step 3 — Generate audio
    print("Step 3/4 — Generating audio...")
    with open(script_path, "r") as f:
        script_text = f.read()

    result = subprocess.run(
        ["python3",
         os.path.expanduser("tts.py"),
         script_text,
         audio_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"TTS failed: {result.stderr}")
        sys.exit(1)
    print(f"✓ Audio saved to {audio_path}\n")

    # Step 4 — Upload
    print("Step 4/4 — Uploading to RSS.com...")
    success = upload_episode(audio_path, script_path)
    if not success:
        print("Upload failed.")
        sys.exit(1)

    print(f"\n{'='*50}")
    print("✓ Pipeline complete!")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run()
