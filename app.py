import streamlit as st
import feedparser
import re
import urllib.parse
from urllib.parse import urlparse
from newspaper import Article, Config
import nltk
import concurrent.futures

# Download the lightweight text processor required for the summarizer
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# Page Config
st.set_page_config(page_title="Tech News Digest", layout="wide", initial_sidebar_state="expanded")

# -------- INITIALIZE SESSION STATE --------
# We do this at the very top so the callback function can use it
if "summarize_clicked" not in st.session_state:
    st.session_state.summarize_clicked = False
if "accessible_articles" not in st.session_state:
    st.session_state.accessible_articles = []

# -------- CALLBACK TO RESET UI --------
# This runs whenever you type a search or change a topic filter
def reset_state():
    st.session_state.summarize_clicked = False
    st.session_state.accessible_articles = []

# -------- CUSTOM CSS FOR MINIMAL/PROFESSIONAL UI --------
st.markdown("""
    <style>
    html, body, .stApp {
        background-color: #dbd9d9 !important;
        color:#1C1C1C !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* LOCK SIDEBAR: Hide the collapse button so it can never be hidden */
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border: 1.5px solid #000000 !important;
        border-radius: 15px !important;
        box-shadow: none !important;
        overflow: hidden !important;
    }

    div[data-testid="stExpander"] details summary:focus,
    div[data-testid="stExpander"] details summary:active,
    div[data-testid="stExpander"] details summary:hover {
        background-color: transparent !important;
        color: #1C1C1C !important;
    }

    .st-expander {
        border: 1px solid #000000 !important;
        border-radius: 8px !important;
    }

    div[data-testid="stExpander"] details summary,
    div[data-testid="stExpander"] details summary:hover,
    div[data-testid="stExpander"] details summary:focus,
    div[data-testid="stExpander"] details summary:active,
    div[data-testid="stExpander"] details[open] summary {
        background-color: transparent !important;
        color: #1C1C1C !important;
    }

    div[data-testid="stExpander"] details summary p,
    div[data-testid="stExpander"] details summary span,
    div[data-testid="stExpander"] details summary svg {
        color: #1C1C1C !important;
        fill: #1C1C1C !important;
    }

    div[data-testid="stContainer"] {
        border: 1px solid #000000 !important;
        border-radius: 15px !important;
    }

    [data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #edebeb !important; 
        border: 1.5px solid #000000 !important; 
        border-radius: 15px !important;
        overflow: hidden !important;
    }
    
    .stColumn > div > div {
        background-color: #edebeb !important;
        border-radius: 15px !important;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        text-align: center;
        margin-top: -3rem;
        color: #000000;
    }

    section[data-testid="stSidebar"] {
        background-color: #2C3947 !important;
        border-right: 1px solid #D0D0D0;
        color: white;
    }

    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] div.stMarkdown,
    section[data-testid="stSidebar"] label p {
        color: #FFFFFF !important;
    }
    
    .sub-title {
        text-align: center;
        font-size: 1.1rem;
        color: #6c757d;
    }
    
    div.stButton > button:first-child {
        background-color: transparent;
        color: #000000;
        border: 2px solid #000000;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        display: block;
        margin: 0 auto;
    }
    
    div.stButton > button:first-child:hover {
        border-color: #000000;
        background-color: #87898c;
    }
    </style>
""", unsafe_allow_html=True)

# -------- SIDEBAR: REFINE --------
st.sidebar.markdown("### ⚙️ Refine")
st.sidebar.write("Customize your news feed.")
st.sidebar.markdown("---")

search_query = st.sidebar.text_input("🔍 Search Titles", placeholder="e.g., OpenAI, chip...", on_change=reset_state)

tech_keywords = [
    "AI", "Cloud", "Cybersecurity",
    "Apple", "Google", "Microsoft", "Startup", "Crypto", "Semiconductor"
]
selected_keywords = st.sidebar.multiselect("🏷️ Topics", tech_keywords, on_change=reset_state)

# -------- MAIN PAGE --------
st.markdown("<div class='main-title'> Tech News Digest</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>ML Based Tech News Dashboard</div>", unsafe_allow_html=True)

# -------- HELPER FUNCTIONS --------
def clean_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def clean_link(link):
    parsed = urlparse(link)
    return parsed.scheme + "://" + parsed.netloc + parsed.path

@st.cache_data(show_spinner=False)
def get_full_article_and_summary(url, rss_fallback_summary=""):
    """
    Returns (full_text, summary, is_accessible).
    Uses the RSS summary as a fallback if the site blocks the scraper.
    """
    # Spoof a real browser to bypass basic anti-bot protections
    config = Config()
    config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    config.request_timeout = 8

    try:
        article = Article(url, config=config)
        article.download()
        article.parse()
        
        # Check length BEFORE running heavy CPU NLP task
        if len(article.text) < 200:
            return "", rss_fallback_summary, False
            
        article.nlp()
        return article.text, article.summary, True
        
    except Exception:
        # Complete failure: return fallback
        return "", rss_fallback_summary, False

def is_article_accessible(url, rss_fallback=""):
    _, _, accessible = get_full_article_and_summary(url, rss_fallback)
    return accessible

# -------- RSS FEEDS --------
rss_feeds = {
    "Economic Times Tech": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",
    "The Hindu Tech": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss",
    "Mint Tech": "https://www.livemint.com/rss/technology",
    "TechCrunch": "https://techcrunch.com/feed/",
    "ZDNET": "https://www.zdnet.com/news/rss.xml",
    "VentureBeat": "https://venturebeat.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml"
}

# -------- COLLECT ARTICLES --------
all_entries = []
seen = set()

for source, url in rss_feeds.items():
    feed = feedparser.parse(url)
    for entry in feed.entries[:15]:
        raw_title = entry.get("title", "No title")
        raw_link = entry.get("link", "#")
        published = entry.get("published", "No date")
        
        # Grab the RSS summary (often stored in 'summary' or 'description')
        raw_summary = entry.get("summary", entry.get("description", "No summary available."))

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
            "source": source,
            "rss_summary": raw_summary
        })

# -------- FILTER BY KEYWORD + SEARCH --------
filtered_entries = []

for news in all_entries:
    title_lower = news["title"].lower()

    matches_search = True
    if search_query:
        matches_search = search_query.lower() in title_lower

    matches_keyword = True
    if selected_keywords:
        matches_keyword = any(kw.lower() in title_lower for kw in selected_keywords)

    if matches_search and matches_keyword:
        filtered_entries.append(news)

filtered_entries = filtered_entries[:50]

# -------- DISPLAY & PROCESSING --------
st.write("---")
st.markdown(f"### 🧾 {len(filtered_entries)} articles found.")

# Helper function for parallel processing
def check_link(news_item):
    is_accessible = is_article_accessible(news_item["link"], news_item["rss_summary"])
    news_item["is_accessible"] = is_accessible
    return news_item

if len(filtered_entries) > 0:
    
    if st.button("Summarize Filtered Articles"):
        st.session_state.summarize_clicked = True
        
        progress = st.empty()
        progress.info("⏳ Parsing articles, please wait...")
        
        valid_articles = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(check_link, filtered_entries)
            for res in results:
                if res is not None:
                    valid_articles.append(res)
        
        st.session_state.accessible_articles = valid_articles
        progress.empty()

    if st.session_state.summarize_clicked:
        final_articles = st.session_state.accessible_articles
        
        st.write("---")
        
        if not final_articles:
            st.error("No articles found.")
        else:
            col1, col2 = st.columns(2)

            for i, news in enumerate(final_articles):
                with (col1 if i % 2 == 0 else col2):
                    with st.container(border=True):
                        st.subheader(news["title"])
                        st.caption(f"📅 {news['published']} | 📰 {news['source']}")
                        st.markdown(f"🔗 [Read Full Article Here]({news['link']})")

                        with st.expander("🔎 View Summary"):
                            full_text, summary, accessible = get_full_article_and_summary(news["link"], news["rss_summary"])
                            
                            if accessible and summary.strip():
                                st.write(summary)
                            elif not accessible:
                                # Custom styled warning matching a softer aesthetic
                                st.markdown(
                                    "<div style='background-color: #fde8ec; padding: 10px; border-radius: 5px; color: #5a3a41;'>"
                                    "<em>Note: The full article is paywalled or blocked. Here is the brief RSS summary:</em></div>", 
                                    unsafe_allow_html=True
                                )
                                # Clean up HTML tags that often come with RSS summaries
                                clean_rss = re.sub('<[^<]+>', '', summary)
                                st.write(clean_rss)
                            else:
                                st.write("Summary unavailable.")
else:
    reset_state()
    st.info("No articles match your search or keyword filters. Try clearing them!")