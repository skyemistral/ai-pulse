"""
AI Pulse — GitHub Actions Automation Script (High Quality Edition)
"""

import feedparser, json, re, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
EMAIL_TO       = os.environ["EMAIL_TO"]
RECIPIENTS     = [e.strip() for e in os.environ.get("RECIPIENTS", EMAIL_TO).split(",")]

DASHBOARD_URL = f"https://{os.environ.get('GITHUB_USERNAME','skyemistral')}.github.io/ai-pulse/"
ARTICLES_FILE = Path("src/articles.json")

# ── HIGH QUALITY SOURCES ──────────────────────────────────────────────────────

VC_FEEDS = {
    "Crunchbase News":    "https://news.crunchbase.com/feed/",
    "TechCrunch Venture": "https://techcrunch.com/category/venture/feed/",
    "Reuters Tech":       "https://feeds.reuters.com/reuters/technologyNews",
    "Fortune Tech":       "https://fortune.com/feed/",
}

AI_STARTUP_FEEDS = {
    "TechCrunch AI":   "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI":  "https://venturebeat.com/category/ai/feed/",
    "The Verge AI":    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "Wired AI":        "https://www.wired.com/feed/tag/artificial-intelligence/rss",
}

INFRA_FEEDS = {
    "The Next Platform":   "https://www.nextplatform.com/feed/",
    "Datacenter Dynamics": "https://www.datacenterdynamics.com/en/rss/",
    "SiliconAngle":        "https://siliconangle.com/feed/",
    "The Register":        "https://www.theregister.com/headlines.rss",
    "Ars Technica":        "https://feeds.arstechnica.com/arstechnica/technology-lab",
}

# ── KEYWORD FILTERS ───────────────────────────────────────────────────────────

VC_KEYWORDS = [
    "raises","raised","funding","acquisition","acquires","acquired",
    "merger","series a","series b","series c","series d","series e",
    "venture capital","ipo","valuation","unicorn","andreessen","sequoia",
    "a16z","general catalyst","lightspeed","softbank","tiger global",
]

VC_MIN_SIGNALS = [
    "$50","$75","$100","$150","$200","$250","$300","$500",
    "$1b","$2b","$3b","$5b","billion","acquisition",
    "acquires","acquired","merger","ipo",
]

AI_STARTUP_KEYWORDS = [
    "out of stealth","launches","unveils","debuts","new model","foundation model",
    "llm","large language model","openai","anthropic","mistral","cohere","xai",
    "grok","deepmind","gemini","claude","gpt","llama","generative ai",
    "ai agent","agentic","reasoning model","multimodal","perplexity",
    "cursor","cognition","humanoid","robotics ai","stealth",
]

INFRA_KEYWORDS = [
    "nvidia","jensen huang","h100","h200","b100","b200","gb200",
    "blackwell","hopper","cuda","nvlink","dgx","hgx",
    "amd","mi300","mi325","mi350","instinct","rocm",
    "data center","gpu cluster","gpu cloud","ai infrastructure",
    "neocloud","coreweave","lambda labs","hyperscaler",
    "microsoft azure","google cloud","aws","amazon web services",
    "inference","training compute","ai chips","semiconductor",
    "infiniband","liquid cooling","ai factory","hpc",
]

BLOCKED_DOMAINS = [
    "github.com","reddit.com","twitter.com","x.com","xcancel.com",
    "news.ycombinator.com","medium.com","youtube.com","linkedin.com",
    "facebook.com","instagram.com","tiktok.com","substack.com",
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def is_blocked(link):
    return any(d in link.lower() for d in BLOCKED_DOMAINS)

def has_vc_signal(title, summary):
    text = (title + " " + summary).lower()
    return any(s in text for s in VC_MIN_SIGNALS)

def fetch_feeds(feeds, keywords, category, cutoff, extra_check=None):
    articles = []
    for source, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry,'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry,'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                if pub_date and pub_date < cutoff:
                    continue
                title   = entry.get('title','')
                summary = entry.get('summary', entry.get('description',''))
                link    = entry.get('link','')
                if is_blocked(link):
                    continue
                text = (title + " " + summary).lower()
                if not any(kw in text for kw in keywords):
                    continue
                if extra_check and not extra_check(title, summary):
                    continue
                clean = re.sub(r'<[^>]+>','', summary)[:400].strip()
                articles.append({
                    "title": title, "source": source, "link": link,
                    "pub_date": pub_date.isoformat() if pub_date else None,
                    "pub_date_str": pub_date.strftime("%b %d, %Y %I:%M %p UTC") if pub_date else "Unknown",
                    "summary": clean, "category": category
                })
                count += 1
            print(f"  ✓ {source}: {count}")
        except Exception as e:
            print(f"  ✗ {source}: {e}")
    return articles

def fetch_articles(cutoff_hours=48):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
    print("💰 VC & Funding feeds...")
    vc = fetch_feeds(VC_FEEDS, VC_KEYWORDS, "Venture Capital & Funding", cutoff, has_vc_signal)
    print("🚀 AI Startup feeds...")
    startups = fetch_feeds(AI_STARTUP_FEEDS, AI_STARTUP_KEYWORDS, "AI Startups & Research", cutoff)
    print("🖥️  Infrastructure feeds...")
    infra = fetch_feeds(INFRA_FEEDS, INFRA_KEYWORDS, "AI Infrastructure", cutoff)
    all_articles = vc + startups + infra
    seen, unique = set(), []
    for a in sorted(all_articles, key=lambda x: x['pub_date'] or '', reverse=True):
        key = a['title'][:60].lower()
        if key not in seen:
            seen.add(key); unique.append(a)
    return unique

# ── EMAIL ─────────────────────────────────────────────────────────────────────

def send_email(articles, new_count):
    pst_tz   = timezone(timedelta(hours=-8))
    now_pst  = datetime.now(pst_tz)
    run_time = now_pst.strftime("%B %d, %Y at %I:%M %p PST")
    session  = "🌅 Morning" if now_pst.hour < 12 else "🌆 Evening"
    total       = len(articles)
    vc_count    = len([a for a in articles if a['category']=="Venture Capital & Funding"])
    infra_count = len([a for a in articles if a['category']=="AI Infrastructure"])
    res_count   = len([a for a in articles if a['category']=="AI Startups & Research"])

    def section(cat, color, icon, limit=6):
        items = [a for a in articles if a['category']==cat][:limit]
        if not items:
            return f"<p style='color:#475569;font-size:0.75rem;padding:0.5rem 0;'>No articles in this category yet.</p>"
        rows = ""
        for a in items:
            t = a['title'][:100] + ("…" if len(a['title']) > 100 else "")
            rows += f"""
            <a href="{a['link']}" style="text-decoration:none;display:block;margin-bottom:1rem;">
              <div style="border-left:3px solid {color};padding-left:0.85rem;">
                <div style="font-size:0.83rem;color:#e2e8f0;font-weight:600;line-height:1.45;margin-bottom:3px;">{t}</div>
                <div style="font-size:0.7rem;color:#64748b;">{icon} {a['source']} · {a['pub_date_str']}</div>
                <div style="font-size:0.75rem;color:#475569;margin-top:4px;line-height:1.5;">{a['summary'][:160]}{'…' if len(a['summary'])>160 else ''}</div>
              </div>
            </a>"""
        return rows

    new_badge = "" if new_count == 0 else f"""
    <div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);
        border-radius:10px;padding:0.65rem 1rem;margin-bottom:1.25rem;
        text-align:center;font-size:0.8rem;color:#a78bfa;">
      🆕 <strong>{new_count} new articles</strong> since last refresh
    </div>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:660px;margin:0 auto;padding:1.5rem;">

  <div style="background:linear-gradient(135deg,#0f0f1a,#1a0a2e);border-radius:16px;
      padding:2rem;margin-bottom:1.25rem;text-align:center;border:1px solid #1e293b;">
    <div style="font-size:2.2rem;margin-bottom:0.5rem;">⚡</div>
    <h1 style="margin:0;font-size:1.7rem;font-weight:800;color:#a78bfa;">AI Pulse</h1>
    <p style="color:#64748b;margin:0.4rem 0 0;font-size:0.82rem;">Real-time intelligence · AI Startups, VC & Infrastructure</p>
    <div style="margin-top:0.85rem;display:inline-block;background:rgba(16,185,129,0.1);
        border:1px solid rgba(16,185,129,0.3);border-radius:20px;padding:0.3rem 0.85rem;
        font-size:0.72rem;color:#10b981;">● LIVE · {session} Edition</div>
    <div style="margin-top:0.5rem;font-size:0.7rem;color:#475569;">{run_time}</div>
  </div>

  <table width="100%" cellpadding="0" cellspacing="8" style="margin-bottom:1.25rem;">
    <tr>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;">
        <div style="font-size:1.4rem;">💰</div>
        <div style="font-size:1.6rem;font-weight:800;color:#10b981;">{vc_count}</div>
        <div style="font-size:0.65rem;color:#64748b;">VC & Funding</div>
      </td>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;">
        <div style="font-size:1.4rem;">🖥️</div>
        <div style="font-size:1.6rem;font-weight:800;color:#3b82f6;">{infra_count}</div>
        <div style="font-size:0.65rem;color:#64748b;">Infrastructure</div>
      </td>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;">
        <div style="font-size:1.4rem;">🚀</div>
        <div style="font-size:1.6rem;font-weight:800;color:#a855f7;">{res_count}</div>
        <div style="font-size:0.65rem;color:#64748b;">Startups & Research</div>
      </td>
    </tr>
  </table>

  {new_badge}

  <div style="text-align:center;margin-bottom:1.5rem;">
    <a href="{DASHBOARD_URL}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#a855f7);
        color:white;text-decoration:none;padding:0.9rem 2.5rem;border-radius:12px;
        font-weight:700;font-size:1rem;box-shadow:0 4px 20px rgba(99,102,241,0.35);">
      ⚡ Open Full Dashboard →
    </a>
  </div>

  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.5rem;margin-bottom:1rem;">
    <div style="font-size:0.85rem;font-weight:700;color:#10b981;margin-bottom:1rem;
        padding-bottom:0.5rem;border-bottom:1px solid #1e293b;">
      💰 Venture Capital & Funding
    </div>
    {section("Venture Capital & Funding","#10b981","💰")}
  </div>

  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.5rem;margin-bottom:1rem;">
    <div style="font-size:0.85rem;font-weight:700;color:#3b82f6;margin-bottom:1rem;
        padding-bottom:0.5rem;border-bottom:1px solid #1e293b;">
      🖥️ AI Infrastructure
    </div>
    {section("AI Infrastructure","#3b82f6","🖥️")}
  </div>

  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.5rem;margin-bottom:1.5rem;">
    <div style="font-size:0.85rem;font-weight:700;color:#a855f7;margin-bottom:1rem;
        padding-bottom:0.5rem;border-bottom:1px solid #1e293b;">
      🚀 AI Startups & Research
    </div>
    {section("AI Startups & Research","#a855f7","🚀")}
  </div>

  <div style="text-align:center;border-top:1px solid #1e293b;padding-top:1rem;">
    <p style="color:#475569;font-size:0.72rem;margin:0;">
      ⏰ Delivered at <strong style="color:#a78bfa;">5:00 AM PST</strong> &
      <strong style="color:#a78bfa;">5:00 PM PST</strong> daily
    </p>
    <p style="color:#334155;font-size:0.68rem;margin:0.3rem 0 0;">
      📰 {total} articles · last 48h · AI Pulse
    </p>
  </div>

</div></body></html>"""

    text = (f"AI Pulse {session} ({run_time})\n\n"
            f"📰 {total} articles · last 48h\n"
            f"💰 VC: {vc_count}  🖥️ Infra: {infra_count}  🚀 Research: {res_count}\n"
            f"🆕 {new_count} new since last refresh\n\n"
            f"→ Dashboard: {DASHBOARD_URL}\n\n"
            + "\n".join(f"• {a['title']}" for a in articles[:10]))

    for recipient in RECIPIENTS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⚡ AI Pulse {session} — {total} Articles | {run_time}"
            msg["From"]    = f"AI Pulse <{GMAIL_USER}>"
            msg["To"]      = recipient
            msg.attach(MIMEText(text,"plain"))
            msg.attach(MIMEText(html,"html"))
            with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
                s.login(GMAIL_USER, GMAIL_APP_PASS)
                s.sendmail(GMAIL_USER, recipient, msg.as_string())
            print(f"  ✅ Email → {recipient}")
        except Exception as e:
            print(f"  ✗ Failed {recipient}: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    pst_tz = timezone(timedelta(hours=-8))
    print(f"\n{'='*55}\n  ⚡ AI Pulse — {datetime.now(pst_tz).strftime('%Y-%m-%d %I:%M %p PST')}\n{'='*55}")
    prev_titles = set()
    if ARTICLES_FILE.exists():
        try: prev_titles = {a['title'][:60].lower() for a in json.loads(ARTICLES_FILE.read_text())}
        except: pass
    articles = fetch_articles(cutoff_hours=48)
    new_count = len([a for a in articles if a['title'][:60].lower() not in prev_titles])
    print(f"\n✅ {len(articles)} articles ({new_count} new)")
    ARTICLES_FILE.parent.mkdir(exist_ok=True)
    ARTICLES_FILE.write_text(json.dumps(articles, indent=2))
    print(f"\n📧 Sending to {len(RECIPIENTS)} recipients...")
    send_email(articles, new_count)
    print(f"{'='*55}\n")

if __name__ == "__main__":
    run()
