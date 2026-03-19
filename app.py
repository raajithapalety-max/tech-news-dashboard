import streamlit as st
import feedparser
import re
from urllib.parse import urlparse
from transformers import pipeline
from newspaper import Article

st.set_page_config(page_title="CS Tech News Dashboard", layout="wide")
st.title("📰 AI Powered CS Tech News Dashboard")

# -------- RSS FEEDS --------
rss_feeds = {
    "The Hindu Tech": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss",
    "Mint Tech": "https://www.livemint.com/rss/technology"
}

# -------- LOAD SUMMARIZER (Cached) --------
@st.cache_resource
def load_summarizer():
    return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

#summarizer = load_summarizer()


# -------- HELPER FUNCTIONS --------
def clean_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def clean_link(link):
    parsed = urlparse(link)
    return parsed.scheme + "://" + parsed.netloc + parsed.path


def get_full_article(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except:
        return ""


def summarize_text(text):
    if len(text) < 200:
        return "Content too short to summarize."

    text = text[:2000]  # truncate long articles

    summary = summarizer(
        text,
        max_length=150,
        min_length=80,
        do_sample=False
    )

    return summary[0]["summary_text"]


# -------- COLLECT ARTICLES --------
all_entries = []
seen = set()

for source, url in rss_feeds.items():
    feed = feedparser.parse(url)

    for entry in feed.entries[:10]:

        raw_title = entry.get("title", "No title")
        raw_link = entry.get("link", "#")
        published = entry.get("published", "No date")

        normalized_title = clean_title(raw_title)
        normalized_link = clean_link(raw_link)

        identifier = (normalized_title, normalized_link)

        if identifier in seen:
            continue

        seen.add(identifier)

        all_entries.append({
            "title": raw_title.strip(),
            "link": raw_link,
            "published": published,
            "source": source
        })

# -------- DISPLAY --------
st.write(f"### 🧾 Unique Articles Found: {len(all_entries)}")

if st.button("🚀 Summarize News"):

    summarizer = load_summarizer()

    for news in all_entries:
        st.subheader(news["title"])
        st.write("📅", news["published"])
        st.write("📰 Source:", news["source"])
        st.markdown(f"[Read Full Article]({news['link']})")

        with st.spinner("Summarizing article..."):
            full_text = get_full_article(news["link"])
            summary = summarize_text(full_text)

            st.write("### 🔎 Summary")
            st.write(summary)

        st.write("---")