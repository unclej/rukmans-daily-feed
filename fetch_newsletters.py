import imaplib
import email
from email import policy
from datetime import date
import json
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import re

dotenv_path = os.path.expanduser(".env")
load_dotenv(dotenv_path)

GMAIL = os.getenv("GMAIL_ADDRESS")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
LABEL = "Newsletters"
MAX_NEWS_LEN = 20000

ad_phrases = [
        # View/browser prompts
        "view email in browser",
        "view in browser",
        "view this email",
        "view online",
        "having trouble viewing",
        "can't see this email",
        "click here to view",
        "read online",
        "open in browser",

        # Subscription management
        "unsubscribe",
        "manage preferences",
        "manage subscription",
        "update preferences",
        "update subscription",
        "email preferences",
        "subscription preferences",
        "opt out",
        "opt-out",
        "remove yourself",
        "no longer wish to receive",
        "snooze this email",
        "pause emails",
        "change frequency",

        # Forwarding/sharing prompts
        "did someone forward you",
        "was this forwarded",
        "forward this email",
        "share this email",
        "share with friends",
        "send to a friend",
        "refer a friend",
        "invite a friend",

        # Sponsor/ad blocks
        "in partnership with",
        "sponsored by",
        "paid partnership",
        "presented by",
        "brought to you by",
        "advertisement",
        "advertiser content",
        "partner content",
        "please support our sponsors",
        "our sponsors make this possible",
        "support our newsletter",
        "this newsletter is free because",
        "affiliate",

        # Legal/footer
        "copyright",
        "all rights reserved",
        "terms of service",
        "terms of use",
        "privacy policy",
        "legal notice",
        "disclaimer",
        "disclosure",

        # Social/follow prompts
        "follow us on",
        "find us on",
        "connect with us",
        "follow on twitter",
        "follow on instagram",
        "subscribe on youtube",
        "like us on facebook",
        "join us on",

        # Mailing address blocks
        "you are receiving this",
        "you received this",
        "you're receiving this",
        "this email was sent to",
        "was sent to you",
        "mailing address",
        "po box",
        "p.o. box",
        "suite 1",
        "suite 2",
        "new york, ny",
        "san francisco, ca",

        # Newsletter-specific CTAs
        "subscribe for free",
        "start your free",
        "get the newsletter",
        "join our newsletter",
        "sign up for free",
        "become a member",
        "upgrade to premium",
        "become a subscriber",
        "support our work",
        "buy us a coffee",
        "tip jar",

        # Feedback prompts
        "let us know what you think",
        "feedback is a gift",
        "we read every email",
        "reply to this email",
        "hit reply",
        "leave a review",
        "rate us",
        "how are we doing",
        "was this useful",
        "did you enjoy",

        # Tracking/pixel noise
        "beacon",
        "tracking pixel",
        "open tracker",

        # Generic footer noise
        "sent with",
        "powered by",
        "email delivered by",
        "sent via",
        "built with",
        "designed by",
        "this message was sent",
    ]


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "img", "head", "footer"]):
        tag.decompose()

    # Remove sponsor/ad blocks
    for tag in soup.find_all(True):
        tag_text = tag.get_text(strip=True).lower()
        if any(phrase in tag_text for phrase in ad_phrases):
            # Only remove if the tag is small enough to be a noise block
            # (don't remove a whole section just because it mentions "subscribe")
            if len(tag_text) < 300:
                tag.decompose()

    # Get clean textP
    text = soup.get_text(separator=" ", strip=True)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r' \. ', '. ', text)

    return text.strip()


def clean_text(text):
    # Strip forwarded message headers
    fwd_markers = [
        "---------- Forwarded message ---------",
        "---------- Forwarded message ----------",
        "Begin forwarded message:",
    ]
    for marker in fwd_markers:
        if marker in text:
            # Keep everything after the forwarded header block
            parts = text.split(marker, 1)
            if len(parts) > 1:
                # Skip the From/Date/Subject/To header lines
                lines = parts[1].split('\n')
                content_lines = []
                header_done = False
                for line in lines:
                    stripped = line.strip()
                    if not header_done:
                        if stripped.startswith(('From:', 'Date:', 'Subject:', 'To:', 'Cc:')):
                            continue
                        elif stripped == '':
                            continue
                        else:
                            header_done = True
                    content_lines.append(line)
                text = '\n'.join(content_lines)

    # Remove invisible/zero-width unicode characters used for tracking
    invisible_chars = [
        '\u2007', '\u034f', '\u00ad', '\u200b', '\u200c',
        '\u200d', '\u200e', '\u200f', '\ufeff', '\u00a0',
    ]
    for char in invisible_chars:
        text = text.replace(char, ' ')

    # Remove inline URLs <https://...> or <http://...>
    text = re.sub(r'<https?://[^\s>]+>', '', text)

    # Remove markdown-style links [text](url)
    text = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', text)

    # Remove image alt text blocks
    text = re.sub(r'\[image:[^\]]*\]', '', text)

    # Remove bare URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove lines that are just noise
    noise_patterns = [
        r'^\s*view in browser\s*$',
        r'^\s*unsubscribe\s*$',
        r'^\s*share\s*$',
        r'^\s*comment\s*$',
        r'^\s*reply\s*$',
        r'^\s*forward\s*$',
        r'^\s*[-_=*]{3,}\s*$',  # divider lines --- === ***
        r'^\s*\*\s*$',          # lone asterisks
        r'^\s*\.\s*$',          # lone periods
    ]
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        skip = False
        for pattern in noise_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Remove footer — everything after common footer markers
    footer_markers = [
        'thanks for reading',
        'you are receiving this',
        'you received this',
        'unsubscribe from this',
        'manage your emails',
        '© 20',
        'copyright © 20',
        'all rights reserved',
        'powered by ghost',
        'our emails are powered',
    ]
    lower_text = text.lower()
    earliest_footer = len(text)
    for marker in footer_markers:
        idx = lower_text.find(marker)
        if idx != -1 and idx < earliest_footer:
            earliest_footer = idx
    text = text[:earliest_footer]

    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()


def fetch_body(msg):
    # Extract body — try plain text first, fall back to HTML
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = clean_text(part.get_content())
                break
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    body = clean_html(part.get_content())
                    break
    else:
        content_type = msg.get_content_type()
        if content_type == "text/html":
            body = clean_html(msg.get_content())
        else:
            body = msg.get_content()

    return body[:MAX_NEWS_LEN].strip()


def fetch_newsletters():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL, APP_PASSWORD)
    mail.select(LABEL)

    # Get today's emails only
    today = date.today().strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'(SINCE "{today}")')

    if not messages[0]:
        print("No newsletters today")
        return []

    newsletters = []
    for msg_id in messages[0].split():
        status, data = mail.fetch(msg_id, '(RFC822)')
        msg = email.message_from_bytes(data[0][1], policy=policy.default)

        sender = msg.get('from', 'Unknown')
        subject = msg.get('subject', 'No subject')

        body = fetch_body(msg)

        newsletters.append({
            "sender": sender,
            "subject": subject,
            "body": body
        })
        print(f"✓ Fetched: {subject}")

    mail.logout()
    return newsletters


if __name__ == "__main__":
    results = fetch_newsletters()
    # Save to a temp JSON file for Hermes to read
    output_path = "/tmp/newsletters.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} newsletters to {output_path}")