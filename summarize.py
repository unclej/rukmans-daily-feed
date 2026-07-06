import json
import os
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv(os.path.expanduser(".env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "google/gemini-3.1-flash-lite-preview"
MAX_CHARS_PER_NEWSLETTER = 10000


def _call_api(prompt, max_tokens=1024):
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    data = response.json()
    if "choices" not in data:
        print(f"API error (HTTP {response.status_code}): {json.dumps(data, indent=2)}")
        return None
    return data["choices"][0]["message"]["content"].strip()


def _extract_highlights(newsletter):
    """Pass 1: Extract key highlights from a single newsletter."""
    body = newsletter["body"][:MAX_CHARS_PER_NEWSLETTER]
    prompt = (
        f"Extract the 6-8 most important stories, insights, or takeaways from this newsletter. "
        f"Be specific and concrete — include names, numbers, and details. "
        f"Return only a bulleted list (no headers, no fluff, no intro sentence).\n\n"
        f"Newsletter from {newsletter['sender']} — \"{newsletter['subject']}\":\n{body}"
    )
    result = _call_api(prompt, max_tokens=1024)
    if not result:
        return None
    return result


def summarize(newsletters_path):
    with open(newsletters_path, "r") as f:
        newsletters = json.load(f)

    if not newsletters:
        print("No newsletters to summarize")
        return None

    today = date.today().strftime("%A, %B %d, %Y")

    # Pass 1: Extract highlights from each newsletter independently
    print(f"Extracting highlights from {len(newsletters)} newsletters...")
    all_highlights = []
    for n in newsletters:
        body = n["body"]
        full_chars = len(body)
        full_words = len(body.split())
        used_chars = min(full_chars, MAX_CHARS_PER_NEWSLETTER)
        used_words = len(body[:MAX_CHARS_PER_NEWSLETTER].split())
        cut_chars = full_chars - used_chars
        stat = f"{used_chars:,} chars / {used_words:,} words"
        if cut_chars > 0:
            stat += f"  [cut {cut_chars:,} chars / {full_words - used_words:,} words]"
        print(f"  Processing: {n['subject'][:55]}  ({stat})")

        highlights = _extract_highlights(n)
        if highlights:
            all_highlights.append({
                "sender": n["sender"],
                "subject": n["subject"],
                "highlights": highlights,
            })
            print(f"  ✓ Done")
        else:
            print(f"  ✗ Failed to extract highlights from: {n['subject'][:60]}")

    if not all_highlights:
        print("No highlights extracted")
        return None

    # Pass 2: Synthesize all highlights into a briefing script
    highlights_block = ""
    for h in all_highlights:
        highlights_block += f"\n\n=== {h['sender']} | {h['subject']} ===\n"
        highlights_block += h["highlights"]

    source_list = ", ".join(h["sender"] for h in all_highlights)

    prompt = (
        "You are writing a spoken morning briefing script to be read aloud by a text-to-speech "
        f"voice. Today is {today}.\n\n"
        f"Here are key highlights from today's newsletters ({source_list}):\n"
        f"{highlights_block}\n\n"
        "Instructions:\n"
        "- Open with a warm greeting and today's date\n"
        "- Cover highlights from ALL of the newsletters above — every source should be represented\n"
        "- If the same story or topic appears in multiple newsletters, cover it once but give it "
        "extra weight — multiple sources signal it's especially significant\n"
        "- Flow naturally between topics with smooth transitions\n"
        "- End with a brief sign-off\n"
        "- Target 10 minutes of speaking time (roughly 1,300-1,500 words)\n"
        "- Use no bullet points, headers, or markdown — pure spoken prose\n"
        "- Never say 'according to the newsletter' — just tell the stories naturally\n\n"
        "Write only the script, nothing else."
    )

    print("Synthesizing briefing script...")
    script = _call_api(prompt, max_tokens=4096)
    if not script:
        return None

    script_path = "/tmp/briefing_script.txt"
    with open(script_path, "w") as f:
        f.write(script)

    print(f"Script written ({len(script.split())} words)")
    print("\n--- PREVIEW (first 300 chars) ---")
    print(script[:300])
    return script_path


if __name__ == "__main__":
    summarize("/tmp/newsletters.json")
