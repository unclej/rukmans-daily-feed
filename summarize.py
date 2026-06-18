import json
import os
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv(os.path.expanduser(".env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "google/gemini-3.1-flash-lite-preview"


def summarize(newsletters_path):
    with open(newsletters_path, "r") as f:
        newsletters = json.load(f)

    if not newsletters:
        print("No newsletters to summarize")
        return None

    today = date.today().strftime("%A, %B %d, %Y")

    # Build the prompt
    newsletter_text = ""
    for n in newsletters:
        newsletter_text += f"\n\n--- {n['sender']} | {n['subject']} ---\n"
        newsletter_text += n["body"]

    prompt = (
        "You are writing a spoken morning briefing script to be read aloud by a text-to-speech"
        "voice. "
        f"Today is {today}.\n\n"
        "Here are today's newsletters:\n"
        f"{newsletter_text}\n\n"
        "Write a natural, conversational spoken script that:\n"
        "- Opens with a warm greeting and today's date\n"
        "- Covers the key stories and ideas from each newsletter\n"
        "- Flows naturally between topics with smooth transitions\n"
        "- Skips ads, subscription pitches, and boilerplate\n"
        "- Ends with a brief sign-off\n"
        "- Is about 3-4 minutes of speaking time (roughly 450-600 words)\n"
        "- Uses no bullet points, headers, or markdown — pure spoken prose\n"
        "- Never says \"according to the newsletter\" — just tell the stories naturally\n\n"
        "Write only the script, nothing else."
    )

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
    )

    data = response.json()
    if "choices" not in data:
        print(f"API error (HTTP {response.status_code}): {json.dumps(data, indent=2)}")
        return None
    script = data["choices"][0]["message"]["content"].strip()

    # Save script to file
    script_path = "/tmp/briefing_script.txt"
    with open(script_path, "w") as f:
        f.write(script)

    print(f"Script written ({len(script.split())} words)")
    print("\n--- PREVIEW (first 300 chars) ---")
    print(script[:300])
    return script_path


if __name__ == "__main__":
    summarize("/tmp/newsletters.json")
