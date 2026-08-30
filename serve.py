import os
import json
from flask import Flask, send_file, Response
from datetime import datetime, timedelta

app = Flask(__name__)

OUTPUT_DIR = os.path.expanduser("~/CardioClaw/output")
EPISODES_FILE = os.path.join(OUTPUT_DIR, "episodes.json")

SERVER_IP = "157.151.155.75"
PORT = 5000
COVER_IMAGE = os.path.expanduser("~/CardioClaw/cover.png")


def load_episodes():
    if not os.path.exists(EPISODES_FILE):
        return []
    with open(EPISODES_FILE, "r") as f:
        return json.load(f)


@app.route("/")
def index():
    episodes = load_episodes()
    return "Cardiology Claw V4.0 — " + str(len(episodes)) + " episode(s) available."


@app.route("/cover.png")
def cover():
    if os.path.exists(COVER_IMAGE):
        return send_file(COVER_IMAGE, mimetype="image/png")
    return "Cover not found", 404


@app.route("/audio/<filename>")
def audio(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="audio/mpeg")
    return "File not found", 404


@app.route("/feed.xml")
def feed():
    episodes = load_episodes()

    if not episodes:
        return Response("No episodes available yet.", status=404)

    now = datetime.now()
    build_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    date_str = now.strftime("%B %d %Y")

    # Cumulative feed: order oldest season/episode first (matches itunes:type
    # serial listening order). Episodes generated before this field existed
    # fall back to sane defaults so the feed doesn't break on old data.
    episodes = sorted(
        episodes,
        key=lambda e: (e.get("season", 0), e.get("season_episode", 0))
    )

    items = ""
    for ep in episodes:
        audio_url = "http://" + SERVER_IP + ":" + str(PORT) + "/audio/" + ep["filename"]
        guid = SERVER_IP + "-" + ep["filename"] + "-" + ep.get("date", date_str).replace(" ", "")
        description = ep["text"][:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        season = ep.get("season", 1)
        season_episode = ep.get("season_episode", 1)

        # pubDate is derived from the episode's own stored generation time (not
        # "now") plus a small per-episode offset, so it's stable across repeated
        # requests and stays correctly ordered both within and across seasons.
        try:
            base_time = datetime.fromisoformat(ep["generated_at"])
        except (KeyError, ValueError):
            base_time = now
        pub_date = base_time + timedelta(seconds=season_episode)

        items += """
    <item>
      <title>""" + ep["title"] + """</title>
      <description>""" + description + """</description>
      <pubDate>""" + pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000") + """</pubDate>
      <enclosure url=\"""" + audio_url + """\" length=\"""" + str(ep["size"]) + """\" type="audio/mpeg"/>
      <guid isPermaLink="false">""" + guid + """</guid>
      <itunes:season>""" + str(season) + """</itunes:season>
      <itunes:episode>""" + str(season_episode) + """</itunes:episode>
    </item>"""

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Cardiology Report</title>
    <description>Nuclear cardiology briefing — each finding as a separate episode</description>
    <language>en-us</language>
    <lastBuildDate>""" + build_date + """</lastBuildDate>
    <itunes:author>Cardiology Claw</itunes:author>
    <itunes:image href="http://""" + SERVER_IP + ":" + str(PORT) + """/cover.png"/>
    <image><url>http://""" + SERVER_IP + ":" + str(PORT) + """/cover.png</url><title>Cardiology Report</title><link>http://""" + SERVER_IP + ":" + str(PORT) + """/</link></image>
    <itunes:category text="Health"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>serial</itunes:type>
    """ + items + """
  </channel>
</rss>"""

    return Response(rss, mimetype="application/rss+xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
