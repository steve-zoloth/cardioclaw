# Cardiology Report — iPhone Setup Guide
## For the listener's helper

This guide sets up a weekly audio podcast on the listener's iPhone.
Once set up, the listener uses only Siri voice commands — no tapping ever needed.

---

## What you are setting up

A private weekly podcast called **Cardiology Report** that delivers a
nuclear cardiology briefing every Monday morning. Each finding is a
separate short episode the listener can skip through by voice.

The feed address is:
```
http://157.151.155.75:5000/feed.xml
```

---

## Option A — Apple Podcasts (already on every iPhone)

### Step 1 — Add the podcast
1. Open the **Podcasts** app (white icon with purple circles)
2. Tap **Library** at the bottom of the screen
3. Tap the **+** button in the top right corner
4. Tap **Follow a Show by URL**
5. Type or paste: `http://157.151.155.75:5000/feed.xml`
6. Tap **Follow** or **Subscribe**
7. The show called **Cardiology Report** will appear in the Library

### Step 2 — Change settings so episodes stay after playing
Without this, episodes disappear after they finish and cannot be replayed.

1. Open the **Settings** app (grey gear icon)
2. Scroll down and tap **Podcasts**
3. Set **Keep Episodes** to **All Episodes**
4. Set **Remove Played Downloads** to **Never** (or turn it Off)
5. Go back — done

### Step 3 — Verify it worked
Tap **Cardiology Report** in the Library. You should see a list of
episodes with titles like "Introduction", "Finding 1 of 8", etc.

---

## Option B — Overcast (recommended for better experience)

Overcast is a free podcast app with clearer audio and better voice control.

### Step 1 — Install Overcast
1. Open the **App Store** (blue icon)
2. Search for **Overcast**
3. Download and install it (it is free)
4. Open Overcast and create a free account or skip

### Step 2 — Add the podcast
1. In Overcast, tap the **+** button or magnifying glass
2. Tap **Add URL**
3. Type or paste: `http://157.151.155.75:5000/feed.xml`
4. Tap **Add to Library**
5. **Cardiology Report** will appear in the podcast list

### Step 3 — Turn on Voice Boost
This makes speech louder and clearer — especially helpful for
medical terminology.

1. Tap **Cardiology Report** in the list
2. Tap the settings icon (top right)
3. Turn on **Voice Boost**
4. Turn on **Smart Speed** (removes silent gaps, slightly faster)

---

## Siri voice commands for the listener

Once set up, the listener uses only these voice commands:

| What to say | What happens |
|---|---|
| "Hey Siri, play Cardiology Report" | Starts the intro episode |
| "Hey Siri, play next episode" | Skips to the next finding **and starts playing it** |
| "Hey Siri, play previous episode" | Goes back one episode and starts playing |
| "Hey Siri, pause" | Pauses playback |
| "Hey Siri, resume" | Resumes where she left off |
| "Hey Siri, play Cardiology Report in Overcast" | Opens in Overcast specifically |

Say **"play"** before "next episode" / "previous episode" — without it, Siri
may cue up the episode without actually starting playback, which means
tapping Play manually. That defeats voice-only use, so the audio itself now
coaches this exact phrasing.

The intro episode announces how many findings there are that week.
Each finding announces its position ("Finding 3 of 8") so the
listener always knows where she is.

---

## What to expect each Monday

New episodes are generated automatically every Monday morning.
The listener's podcast app refreshes on its own — she does not need
to do anything. Saying "Hey Siri, play Cardiology Report" on Monday
will play the new week's briefing.

---

## If something is not working

Contact Steve Zoloth at zoloth1@verizon.net
