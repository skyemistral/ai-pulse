"""
AI Pulse — GitHub Actions Automation Script
"""
import feedparser, json, re, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
EMAIL_TO       = os.environ["EMAIL_TO"]

DASHBOARD_URL = "https://storage.googleapis.com/agenthub/uid-8tJzkxAc4PWtwg5iEf8KLhf5AMT2/custom_agent_interactions/uffQf9chnYzsE4U49CxxWS/output/ai_pulse_dashboard.html"
ARTICLES_FILE = Path("src/articles.json")

RSS_FEEDS = {
    "TechCrunch AI":       "https://techcrunch.com/category/artificial-intelligence/feed/",
    "TechCrunch Startups": "https://techcrunch.com/category/startups/feed/",
    "VentureBeat AI":      "https://venturebeat.com/category/ai/feed/",
    "The Verge AI":        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "Wired AI":            "https://www.wired.com/feed/tag/artificial-intelligence/rss",
    "Ars Technica":        "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "MIT Tech Review":     "https://www.technologyreview.com/feed/",
    "Reuters Tech":        "https://feeds.reuters.com/reuters/technologyNews",
    "Hacker News":         "https://hnrss.org/newest?q=AI+startup+OR+LLM+OR+venture+capital+OR+GPU&points=50",
    "SiliconAngle":        "https://siliconangle.com/feed/",
}

AI_KEYWORDS = [
    "artificial intelligence", " ai ", "machine learning", "llm", "large language model",
    "openai", "anthropic", "deepmind", "mistral", "generative ai", "genai",
    "venture capital", "series a", "series b", "series c", "funding round", "raises",
    "valuation", "unicorn", "investment", "vc fund", "andreessen", "sequoia", "a16z",
    "ai infrastructure", "gpu", "nvidia", "h100", "a100", "data center",
    "ai chip", "semiconductor", "inference", "training compute", "foundation model",
    "ai agent", "agentic", "reasoning model", "multimodal", "deep learning",
    "cohere", "xai", "grok", "gemini", "claude", "gpt-", "copilot",
]

def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in AI_KEYWORDS)

def categorize(title, summary):
    text = (title + " " + summary).lower()
    if any(k in text for k in ["venture capital","series a","series b","series c","funding",
            "raises $","raises million","valuation","unicorn","vc fund",
            "andreessen","sequoia","a16z","backed","invested"]):
        return "Venture Capital & Funding"
    if any(k in text for k in ["infrastructure","gpu","nvidia","h100","a100","data center",
            "chip","semiconductor","inference","training compute","hardware","cluster"]):
        return "AI Infrastructure"
    return "AI Startups & Research"

def fetch_articles(cutoff_hours=48):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                if pub_date and pub_date < cutoff:
                    continue
                title   = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))
                link    = entry.get('link', '')
                if not is_relevant(title, summary):
                    continue
                clean = re.sub(r'<[^>]+>', '', summary)[:350].strip()
                articles.append({
                    "title": title, "source": source, "link": link,
                    "pub_date": pub_date.isoformat() if pub_date else None,
                    "pub_date_str": pub_date.strftime("%b %d, %Y %I:%M %p UTC") if pub_date else "Unknown",
                    "summary": clean,
                    "category": categorize(title, summary)
                })
                count += 1
            print(f"  v {source}: {count}")
        except Exception as e:
            print(f"  x {source}: {e}")
    seen, unique = set(), []
    for a in sorted(articles, key=lambda x: x['pub_date'] or '', reverse=True):
        key = a['title'][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique

def send_email(articles, new_count):
    pst_tz   = timezone(timedelta(hours=-8))
    now_pst  = datetime.now(pst_tz)
    run_time = now_pst.strftime("%B %d, %Y at %I:%M %p PST")
    session  = "Morning" if now_pst.hour < 12 else "Evening"
    total        = len(articles)
    vc_count     = len([a for a in articles if a['category'] == "Venture Capital & Funding"])
    infra_count  = len([a for a in articles if a['category'] == "AI Infrastructure"])
    res_count    = len([a for a in articles if a['category'] == "AI Startups & Research"])

    def headline_rows(cat, color, icon):
        items = [a for a in articles if a['category'] == cat][:3]
        rows = ""
        for a in items:
            t = a['title'][:85] + ("..." if len(a['title']) > 85 else "")
            rows += f'<a href="{a["link"]}" style="text-decoration:none;display:block;margin-bottom:0.75rem;"><div style="border-left:3px solid {color};padding-left:0.75rem;"><div style="font-size:0.82rem;color:#e2e8f0;font-weight:600;line-height:1.4;">{t}</div><div style="font-size:0.7rem;color:#64748b;margin-top:3px;">{icon} {a["source"]} · {a["pub_date_str"]}</div></div></a>'
        return rows or "<p style='color:#475569;font-size:0.75rem;'>No articles yet.</p>"

    new_badge = "" if new_count == 0 else f'<div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);border-radius:10px;padding:0.65rem 1rem;margin-bottom:1.25rem;text-align:center;font-size:0.8rem;color:#a78bfa;">New: <strong>{new_count} new articles</strong> since last refresh</div>'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:620px;margin:0 auto;padding:1.5rem;">
  <div style="background:linear-gradient(135deg,#0f0f1a,#1a0a2e);border-radius:16px;padding:2rem;margin-bottom:1.25rem;text-align:center;border:1px solid #1e293b;">
    <div style="font-size:2.2rem;">&#9889;</div>
    <h1 style="margin:0;font-size:1.7rem;font-weight:800;color:#a78bfa;">AI Pulse</h1>
    <p style="color:#64748b;margin:0.4rem 0 0;font-size:0.82rem;">Real-time intelligence - AI Startups, VC & Infrastructure</p>
    <div style="margin-top:0.85rem;display:inline-block;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:20px;padding:0.3rem 0.85rem;font-size:0.72rem;color:#10b981;">LIVE - {session} Edition</div>
    <div style="margin-top:0.5rem;font-size:0.7rem;color:#475569;">{run_time}</div>
  </div>
  <table width="100%" cellpadding="0" cellspacing="8" style="margin-bottom:1.25rem;">
    <tr>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;"><div style="font-size:1.4rem;">&#128176;</div><div style="font-size:1.5rem;font-weight:800;color:#10b981;">{vc_count}</div><div style="font-size:0.65rem;color:#64748b;">VC & Funding</div></td>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;"><div style="font-size:1.4rem;">&#128421;</div><div style="font-size:1.5rem;font-weight:800;color:#3b82f6;">{infra_count}</div><div style="font-size:0.65rem;color:#64748b;">Infrastructure</div></td>
      <td style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1rem;text-align:center;"><div style="font-size:1.4rem;">&#128640;</div><div style="font-size:1.5rem;font-weight:800;color:#a855f7;">{res_count}</div><div style="font-size:0.65rem;color:#64748b;">Startups & Research</div></td>
    </tr>
  </table>
  {new_badge}
  <div style="text-align:center;margin-bottom:1.5rem;">
    <a href="{DASHBOARD_URL}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#a855f7);color:white;text-decoration:none;padding:0.9rem 2.5rem;border-radius:12px;font-weight:700;font-size:1rem;">Open Full Dashboard &rarr;</a>
  </div>
  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-bottom:1rem;">
    <div style="font-size:0.82rem;font-weight:700;color:#10b981;margin-bottom:0.85rem;">Top VC & Funding Moves</div>
    {headline_rows("Venture Capital & Funding", "#10b981", "")}
  </div>
  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-bottom:1rem;">
    <div style="font-size:0.82rem;font-weight:700;color:#3b82f6;margin-bottom:0.85rem;">AI Infrastructure Updates</div>
    {headline_rows("AI Infrastructure", "#3b82f6", "")}
  </div>
  <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.25rem;margin-bottom:1.5rem;">
    <div style="font-size:0.82rem;font-weight:700;color:#a855f7;margin-bottom:0.85rem;">Top Startup & Research Stories</div>
    {headline_rows("AI Startups & Research", "#a855f7", "")}
  </div>
  <div style="text-align:center;border-top:1px solid #1e293b;padding-top:1rem;">
    <p style="color:#475569;font-size:0.72rem;margin:0;">Delivered at 5:00 AM PST & 5:00 PM PST daily</p>
    <p style="color:#334155;font-size:0.68rem;margin:0.3rem 0 0;">{total} articles - last 48h - AI Pulse for Skye Hart</p>
  </div>
</div></body></html>"""

    text = f"AI Pulse {session} ({run_time})\n\n{total} articles - last 48h\nVC: {vc_count} | Infra: {infra_count} | Research: {res_count}\n{new_count} new since last refresh\n\nDashboard: {DASHBOARD_URL}\n\n" + "\n".join(f"- {a['title']}" for a in articles[:8])

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Pulse {session} - {total} Articles | {run_time}"
    msg["From"]    = f"AI Pulse <{GMAIL_USER}>"
    msg["To"] = ", ".join(EMAIL_TO.split(","))
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, EMAIL_TO.split(","), msg.as_string())
    print(f"  Email sent to {EMAIL_TO}")

def run():
    pst_tz = timezone(timedelta(hours=-8))
    print(f"\n{'='*55}\n  AI Pulse - {datetime.now(pst_tz).strftime('%Y-%m-%d %I:%M %p PST')}\n{'='*55}")
    prev_titles = set()
    if ARTICLES_FILE.exists():
        try:
            prev_titles = {a['title'][:60].lower() for a in json.loads(ARTICLES_FILE.read_text())}
        except: pass
    print("Fetching feeds...")
    articles = fetch_articles(cutoff_hours=48)
    new_count = len([a for a in articles if a['title'][:60].lower() not in prev_titles])
    print(f"{len(articles)} articles ({new_count} new)")
    ARTICLES_FILE.parent.mkdir(exist_ok=True)
    ARTICLES_FILE.write_text(json.dumps(articles, indent=2))
    print(f"Sending email to {EMAIL_TO}...")
    send_email(articles, new_count)
    print(f"{'='*55}\n")

if __name__ == "__main__":
    run()
