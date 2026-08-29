import os
import re
import json
import subprocess
import feedparser
from openai import OpenAI
from Bio import Entrez
from anthropic import Anthropic
from datetime import datetime, timedelta

# =============================================================================
# CARDIOLOGY CLAW V4.0 — Nuclear Cardiology Briefing for Blind MD User
# Two-layer audio: Headline + Full Abstract per finding
# Each finding is its own RSS episode (Siri "next episode" navigates findings)
# =============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

Entrez.email = "zoloth1@verizon.net"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")
ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD", "")

MAX_NUCLEAR_ARTICLES = 8
MAX_GENERAL_ARTICLES = 6
MAX_RSS_ITEMS = 2
MAX_FINDINGS = 8
MAX_ABSTRACT_CHARS = 12000

OUTPUT_DIR = os.path.expanduser("~/CardioClaw/output")
EPISODES_FILE = os.path.join(OUTPUT_DIR, "episodes.json")
BACKUP_DIR = os.path.expanduser("~/CardioClaw/output_prev")
FFMPEG_PATH = "/usr/local/bin/ffmpeg"

CLAUDE_MODEL = "claude-sonnet-4-6"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_VOICE = "nova"
OPENAI_TTS_INSTRUCTIONS = (
    "Speak clearly and professionally at a measured, calm pace. "
    "You are a knowledgeable medical colleague briefing a physician. "
    "Pronounce medical terminology carefully and accurately. "
    "Pause naturally between sentences. Do not rush."
)

NUCLEAR_CARDIOLOGY_TERMS = (
    "nuclear cardiology[MeSH Terms] OR cardiac PET OR "
    "myocardial perfusion imaging OR cardiac SPECT OR "
    "coronary flow reserve OR cardiac amyloid OR "
    "cardiac sarcoidosis OR radionuclide ventriculography OR "
    "PET myocardial OR flurpiridaz OR "
    "cardiac molecular imaging OR myocardial blood flow"
)

GENERAL_CARDIOLOGY_TERMS = (
    "cardiology AND ("
    "randomized controlled trial[pt] OR "
    "guideline[pt] OR "
    "meta-analysis[pt] OR "
    "practice guideline[pt]"
    ")"
)

GOOGLE_NEWS_FEEDS = {
    "Nuclear Cardiology News":   "https://news.google.com/rss/search?q=nuclear+cardiology&hl=en-US&gl=US&ceid=US:en",
    "Cardiac PET News":          "https://news.google.com/rss/search?q=cardiac+PET+imaging&hl=en-US&gl=US&ceid=US:en",
    "ASNC News":                 "https://news.google.com/rss/search?q=ASNC+nuclear+cardiology&hl=en-US&gl=US&ceid=US:en",
    "Myocardial Perfusion News": "https://news.google.com/rss/search?q=myocardial+perfusion+imaging&hl=en-US&gl=US&ceid=US:en",
}

GENERAL_FEEDS = {
    "Journal of Nuclear Medicine": "https://jnm.snmjournals.org/rss/ahead.xml",
    "BMJ Heart":                   "https://heart.bmj.com/rss/current.xml",
    "AHA Circulation":             "https://www.ahajournals.org/action/showFeed?type=etoc&feed=rss&jc=circ",
}

DAILY_FEEDS = {
    "Journal of Nuclear Medicine": "https://jnm.snmjournals.org/rss/ahead.xml",
    "BMJ Heart":                   "https://heart.bmj.com/rss/current.xml",
    "AHA Circulation":             "https://www.ahajournals.org/action/showFeed?type=etoc&feed=rss&jc=circ",
}


def fetch_rss_content(feeds, label, max_items_per_feed=MAX_RSS_ITEMS):
    print(f"DEBUG: Fetching {len(feeds)} {label} feed(s)...")
    all_content = []
    for name, url in feeds.items():
        try:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            if not feed.entries:
                print(f"  {name}: no entries.")
                continue
            items = feed.entries[:max_items_per_feed]
            print(f"  {name}: {len(items)} item(s).")
            for item in items:
                title = item.get("title", "No title")
                summary = item.get("summary", item.get("description", ""))
                summary = re.sub(r"<[^>]+>", " ", summary).strip()
                summary = " ".join(summary.split())[:300]
                all_content.append(f"[{name}] {title}\n{summary}")
        except Exception as e:
            print(f"  {name}: Failed — {e}")
    print(f"DEBUG: {label} RSS total — {len(all_content)} item(s).")
    return "\n\n".join(all_content)


def search_pubmed(search_term, from_date, to_date, max_results):
    full_term = f"({search_term}) AND {from_date}:{to_date}[Publication Date]"
    print(f"DEBUG: PubMed search ({max_results} max)...")
    with Entrez.esearch(db="pubmed", term=full_term, retmax=max_results) as handle:
        record = Entrez.read(handle)
    ids = record["IdList"]
    print(f"DEBUG: Found {len(ids)} article(s).")
    return ids


def fetch_pubmed_abstracts(ids):
    if not ids:
        return ""
    print(f"DEBUG: Fetching {len(ids)} abstracts...")
    with Entrez.efetch(db="pubmed", id=ids, rettype="abstract", retmode="text") as handle:
        raw_text = handle.read()
    raw_text = raw_text[:MAX_ABSTRACT_CHARS]
    print(f"DEBUG: Received {len(raw_text)} characters.")
    return raw_text


def summarize_with_claude(content, briefing_type, timeframe, total_sources):
    print(f"DEBUG: Sending to {CLAUDE_MODEL}...")
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    today_str = datetime.now().strftime("%B %d, %Y")
    day_name = datetime.now().strftime("%A")

    if briefing_type == "weekly":
        scope = "the past 7 days"
        briefing_label = "weekly"
    else:
        scope = timeframe
        briefing_label = "daily"

    prompt = (
        f"Nuclear cardiology {briefing_label} briefing for a blind physician. "
        f"Today is {day_name}, {today_str}. Content covers {scope}.\n\n"
        f"Return EXACTLY {MAX_FINDINGS} findings. Use ONLY this format, nothing else:\n"
        f"FINDING_1_HEADLINE|one sentence max 30 words naming source and key result\n"
        f"FINDING_1_ABSTRACT|120-150 word spoken prose. Background, methods, results, conclusion. Plain text only.\n"
        f"FINDING_2_HEADLINE|one sentence\n"
        f"FINDING_2_ABSTRACT|120-150 words\n"
        f"...through FINDING_{MAX_FINDINGS}\n\n"
        f"RULES:\n"
        f"- Plain text only, no markdown, no symbols\n"
        f"- FINDING_1 through FINDING_5 MUST be nuclear cardiology (PET, SPECT, myocardial perfusion, cardiac amyloid, cardiac sarcoidosis, nuclear tracers, radiotracers)\n"
        f"- General cardiology, AI/ECG studies, and non-imaging research go LAST (FINDING_6 through FINDING_8 only)\n"
        f"- Use Google News ONLY for ASNC or SNMMI society announcements not in PubMed\n"
        f"- Return ALL {MAX_FINDINGS} findings, do not stop early\n\n"
        f"Content:\n\n{content}"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text
    print(f"DEBUG: Raw response ({len(raw)} chars).")
    return raw


def parse_findings(raw_text):
    findings = []
    headlines = {}
    abstracts = {}

    lines = raw_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "_HEADLINE|" in line:
            try:
                tag, text = line.split("|", 1)
                num = tag.replace("FINDING_", "").replace("_HEADLINE", "")
                headlines[num] = text.strip()
            except Exception as e:
                print(f"  Headline parse error: {line[:50]} — {e}")
        elif "_ABSTRACT|" in line:
            try:
                tag, text = line.split("|", 1)
                num = tag.replace("FINDING_", "").replace("_ABSTRACT", "")
                abstracts[num] = text.strip()
            except Exception as e:
                print(f"  Abstract parse error: {line[:50]} — {e}")

    # Pair headlines and abstracts
    for num in sorted(headlines.keys(), key=lambda x: int(x)):
        headline = headlines.get(num, "")
        abstract = abstracts.get(num, "")
        if headline:
            findings.append({
                "headline": headline,
                "abstract": abstract,
                "source": "Cardiology Journal"
            })

    print(f"DEBUG: Parsed {len(findings)} finding(s).")
    return findings


def generate_tts(client, text, filepath):
    """Generate a single TTS MP3 file."""
    response = client.audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_VOICE,
        input=text,
        instructions=OPENAI_TTS_INSTRUCTIONS
    )
    response.stream_to_file(filepath)
    return os.path.getsize(filepath)


def concat_mp3s(segment_files, output_path):
    """Concatenate MP3 segments into one file (no re-encoding, no chapters —
    each output file here becomes its own separate RSS episode)."""
    concat_file = output_path + ".concat.txt"
    try:
        with open(concat_file, "w") as f:
            for seg in segment_files:
                f.write(f"file '{seg}'\n")

        result = subprocess.run([
            FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c", "copy", output_path
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ffmpeg concat error: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"  concat_mp3s error: {e}")
        return False
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)


def generate_audio(findings, briefing_type, today_str, day_name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)
    date_tag = datetime.now().strftime("%Y%m%d")
    tmp_dir = os.path.join(OUTPUT_DIR, "tmp_segments")
    os.makedirs(tmp_dir, exist_ok=True)

    backup_current_episodes()

    # Clear old episode files
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("episode_") and f.endswith(".mp3"):
            os.remove(os.path.join(OUTPUT_DIR, f))
    if os.path.exists(EPISODES_FILE):
        os.remove(EPISODES_FILE)

    total = len(findings)
    briefing_label = "weekly" if briefing_type == "weekly" else "daily"
    episode_meta = []

    # --- Introduction episode ---
    intro_text = (
        f"Good morning. Today is {day_name}, {today_str}. "
        f"This is your {briefing_label} nuclear cardiology briefing. "
        f"You have {total} finding{'s' if total != 1 else ''} today. "
        f"Nuclear cardiology findings appear first, followed by general cardiology. "
        f"Each finding is its own episode with a headline followed by the full abstract. "
        f"Say next episode at any time to move to the next finding."
    )
    print(f"DEBUG: Generating intro...")
    intro_filename = f"episode_00_intro_{date_tag}.mp3"
    intro_path = os.path.join(OUTPUT_DIR, intro_filename)
    intro_size = generate_tts(client, intro_text, intro_path)
    episode_meta.append({
        "filename": intro_filename,
        "title": f"Introduction — {today_str}",
        "text": intro_text[:500],
        "type": "intro",
        "date": today_str,
        "size": intro_size
    })

    # --- One episode per finding (headline + abstract, concatenated) ---
    for i, finding in enumerate(findings, 1):
        position = f"Finding {i} of {total}. "
        pause_cue = " Abstract follows. Say next episode to skip." if i < total else " Abstract follows."
        headline_text = position + finding["headline"] + pause_cue
        abstract_text = "Full abstract. " + finding["abstract"]

        print(f"DEBUG: Generating finding {i} headline...")
        headline_path = os.path.join(tmp_dir, f"seg_{i:02d}_headline.mp3")
        generate_tts(client, headline_text, headline_path)

        print(f"DEBUG: Generating finding {i} abstract...")
        abstract_path = os.path.join(tmp_dir, f"seg_{i:02d}_abstract.mp3")
        generate_tts(client, abstract_text, abstract_path)

        finding_filename = f"episode_{i:02d}_finding_{date_tag}.mp3"
        finding_path = os.path.join(OUTPUT_DIR, finding_filename)
        print(f"DEBUG: Combining finding {i} into its own episode...")
        ok = concat_mp3s([headline_path, abstract_path], finding_path)
        if not ok:
            # Fall back to headline-only audio rather than failing the whole run
            os.rename(headline_path, finding_path)
        finding_size = os.path.getsize(finding_path)

        episode_meta.append({
            "filename": finding_filename,
            "title": f"Finding {i} of {total}: {finding['headline'][:80]}",
            "text": (finding["headline"] + " " + finding["abstract"])[:500],
            "type": "finding",
            "date": today_str,
            "size": finding_size
        })

    # --- Conclusion episode ---
    outro_text = (
        f"That concludes your {briefing_label} nuclear cardiology briefing "
        f"for {day_name}, {today_str}. "
        f"You heard {total} finding{'s' if total != 1 else ''} today. "
        f"Have a good day."
    )
    print(f"DEBUG: Generating outro...")
    outro_filename = f"episode_{total+1:02d}_outro_{date_tag}.mp3"
    outro_path = os.path.join(OUTPUT_DIR, outro_filename)
    outro_size = generate_tts(client, outro_text, outro_path)
    episode_meta.append({
        "filename": outro_filename,
        "title": f"Conclusion — {today_str}",
        "text": outro_text[:500],
        "type": "outro",
        "date": today_str,
        "size": outro_size
    })

    # Clean up tmp segments
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    with open(EPISODES_FILE, "w") as f:
        json.dump(episode_meta, f, indent=2)

    print(f"\nSuccess: {len(episode_meta)} episodes generated (intro + {total} findings + outro).")
    return episode_meta


def generate_error_episode(message, today_str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)
    filename = "episode_00_error.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        response = client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_VOICE,
            input=message,
            instructions=OPENAI_TTS_INSTRUCTIONS
        )
        response.stream_to_file(filepath)
        size = os.path.getsize(filepath)
        episodes = [{
            "filename": filename,
            "title": f"System Message — {today_str}",
            "text": message,
            "type": "error",
            "date": today_str,
            "size": size
        }]
        with open(EPISODES_FILE, "w") as f:
            json.dump(episodes, f, indent=2)
    except Exception as e:
        print(f"Error episode generation failed: {e}")


def send_alert_email(subject, body):
    if not all([ALERT_EMAIL_TO, ALERT_EMAIL_FROM, ALERT_EMAIL_PASSWORD]):
        print("Email alert skipped — credentials not configured in .env")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = f"[Cardio Claw] {subject}"
        msg["From"] = ALERT_EMAIL_FROM
        msg["To"] = ALERT_EMAIL_TO
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL_FROM, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, ALERT_EMAIL_TO, msg.as_string())
        print(f"Alert email sent: {subject}")
    except Exception as e:
        print(f"Alert email failed (non-fatal): {e}")


def backup_current_episodes():
    if not os.path.exists(EPISODES_FILE):
        return
    try:
        import shutil
        os.makedirs(BACKUP_DIR, exist_ok=True)
        for f in os.listdir(BACKUP_DIR):
            os.remove(os.path.join(BACKUP_DIR, f))
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("episode_") and f.endswith(".mp3"):
                shutil.copy2(os.path.join(OUTPUT_DIR, f), os.path.join(BACKUP_DIR, f))
        shutil.copy2(EPISODES_FILE, os.path.join(BACKUP_DIR, "episodes.json"))
        print("DEBUG: Current episodes backed up to output_prev/")
    except Exception as e:
        print(f"DEBUG: Backup failed (non-fatal): {e}")


def restore_backup_episodes():
    backup_json = os.path.join(BACKUP_DIR, "episodes.json")
    if not os.path.exists(backup_json):
        print("DEBUG: No backup episodes available to restore.")
        return False
    try:
        import shutil
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("episode_") and f.endswith(".mp3"):
                os.remove(os.path.join(OUTPUT_DIR, f))
        if os.path.exists(EPISODES_FILE):
            os.remove(EPISODES_FILE)
        for f in os.listdir(BACKUP_DIR):
            shutil.copy2(os.path.join(BACKUP_DIR, f), os.path.join(OUTPUT_DIR, f))
        print("DEBUG: Previous episodes restored from output_prev/")
        return True
    except Exception as e:
        print(f"DEBUG: Restore failed: {e}")
        return False


def main():
    today = datetime.now()
    is_monday = today.weekday() == 0
    briefing_type = "weekly" if is_monday else "daily"
    today_str = today.strftime("%B %d, %Y")
    day_name = today.strftime("%A")

    print("=" * 60)
    print(f"  CARDIOLOGY CLAW V4.0 — OpenAI TTS — Per-Finding Episodes")
    print(f"  {today.strftime('%A, %B %d %Y at %I:%M %p')}")
    print("=" * 60)

    if not ANTHROPIC_API_KEY or not OPENAI_API_KEY:
        print("ERROR: API keys not configured. Check .env file.")
        send_alert_email("FAILED — API keys missing",
            f"Cardio Claw failed on {day_name}, {today_str}. API keys not set.")
        return

    yesterday_str = (today - timedelta(days=1)).strftime("%Y/%m/%d")
    today_date_str = today.strftime("%Y/%m/%d")
    thirty_days_str = (today - timedelta(days=30)).strftime("%Y/%m/%d")
    seven_days_str = (today - timedelta(days=7)).strftime("%Y/%m/%d")

    if is_monday:
        from_date = seven_days_str
        to_date = today_date_str
        timeframe = "the past 7 days"
        journal_feeds = GENERAL_FEEDS
    else:
        from_date = yesterday_str
        to_date = today_date_str
        timeframe = "yesterday"
        journal_feeds = DAILY_FEEDS

    try:
        google_content = fetch_rss_content(GOOGLE_NEWS_FEEDS, "Google News")
        journal_content = fetch_rss_content(journal_feeds, "Journal")

        print("\nSearching PubMed — nuclear cardiology...")
        nuclear_ids = search_pubmed(NUCLEAR_CARDIOLOGY_TERMS, from_date, to_date, MAX_NUCLEAR_ARTICLES)

        print("Searching PubMed — general cardiology high impact...")
        general_ids = search_pubmed(GENERAL_CARDIOLOGY_TERMS, from_date, to_date, MAX_GENERAL_ARTICLES)

        if not is_monday and not nuclear_ids and not general_ids:
            print("Nothing from yesterday. Falling back to 30 days...")
            from_date = thirty_days_str
            timeframe = "the past 30 days"
            nuclear_ids = search_pubmed(NUCLEAR_CARDIOLOGY_TERMS, from_date, today_date_str, MAX_NUCLEAR_ARTICLES)
            general_ids = search_pubmed(GENERAL_CARDIOLOGY_TERMS, from_date, today_date_str, MAX_GENERAL_ARTICLES)

        nuclear_content = fetch_pubmed_abstracts(nuclear_ids)
        general_content = fetch_pubmed_abstracts(general_ids)

        combined = ""
        source_count = 0

        if nuclear_content:
            combined += "=== PRIMARY: NUCLEAR CARDIOLOGY — PUBMED ===\n\n" + nuclear_content + "\n\n"
            source_count += len(nuclear_ids)

        if general_content:
            combined += "=== PRIMARY: GENERAL CARDIOLOGY — PUBMED ===\n\n" + general_content + "\n\n"
            source_count += len(general_ids)

        if journal_content:
            combined += "=== JOURNAL RSS ===\n\n" + journal_content + "\n\n"
            source_count += 1

        if google_content:
            combined += (
                "=== SECONDARY: NUCLEAR CARDIOLOGY NEWS ===\n"
                "Use only for society announcements or regulatory news not in PubMed above.\n\n"
                + google_content
            )
            source_count += 1

        combined = combined[:25000]

        if not combined.strip():
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"This is your {briefing_type} nuclear cardiology briefing. "
                f"There are no new findings available today. Please check back tomorrow."
            )
            generate_error_episode(msg, today_str)
            return

        raw = summarize_with_claude(combined, briefing_type, timeframe, source_count)
        findings = parse_findings(raw)

        if not findings:
            print("ERROR: No findings parsed.")
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"The briefing system encountered a formatting error. "
                f"Please check the system logs."
            )
            generate_error_episode(msg, today_str)
            return

        episode_meta = generate_audio(findings, briefing_type, today_str, day_name)

        send_alert_email(
            f"OK — {len(findings)} findings — {today_str}",
            f"Cardio Claw V4 ran successfully on {day_name}, {today_str}.\n\n"
            f"{len(findings)} findings with headlines and abstracts.\n\n"
            f"Feed: http://157.151.155.75:5000/feed.xml"
        )

        print("\n--- FINDINGS GENERATED ---")
        for i, f in enumerate(findings, 1):
            print(f"  {i}. {f['headline'][:80]}...")
        print("-" * 40)

    except Exception as e:
        import traceback
        print(f"\nSystem Error: {str(e)}")
        traceback.print_exc()

        restored = restore_backup_episodes()
        restore_note = (
            "Previous week's episodes have been restored to the feed."
            if restored else "No backup episodes were available."
        )

        send_alert_email(
            f"FAILED — {today_str}",
            f"Cardio Claw V4 failed on {day_name}, {today_str}.\n\n"
            f"Error: {str(e)}\n\n{restore_note}\n\n"
            f"Check log: ~/CardioClaw/cardio_claw.log"
        )

        if not restored:
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"The cardiology briefing system encountered an error "
                f"and was unable to generate this week's findings. "
                f"Please check the system logs."
            )
            try:
                generate_error_episode(msg, today_str)
            except Exception:
                pass


if __name__ == "__main__":
    main()
