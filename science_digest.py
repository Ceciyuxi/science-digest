#!/usr/bin/env python3
"""
Science Digest - Daily Natural Sciences News Aggregator

Fetches top articles from FREE, publicly accessible science news sources,
categorizes them by scientific domain (Astronomy, Biology, Climate), and
generates simple explanations at a 7th grade reading level.

Only uses open access sources - no paywalled content from Nature, Science, etc.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import os
import sys
import webbrowser
import time
import re

# Mountain Time is UTC-7 (MST) or UTC-6 (MDT during daylight saving)
# Using UTC-7 as default (standard time)
MOUNTAIN_TZ = timezone(timedelta(hours=-7))

# Configuration
OUTPUT_FILE = "science_digest.html"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# NASA API (DEMO_KEY has limited requests, get free key at api.nasa.gov)
NASA_API_KEY = "DEMO_KEY"
NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"

# Nature/Science RSS Feeds with images
NATURE_RSS_FEEDS = [
    # Smithsonian has great nature/science content with images
    "https://www.smithsonianmag.com/rss/science-nature/",
    # BBC Science & Environment
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
]
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Domains/URLs known to have paywalls - always skip these
PAYWALLED_DOMAINS = [
    "nature.com",
    "science.org",
    "sciencemag.org",
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "newscientist.com",
    "scientificamerican.com",
    "theatlantic.com",
    "wired.com",
]

# Paywall indicators in page content
PAYWALL_INDICATORS = [
    "subscribe to read",
    "subscription required",
    "premium content",
    "members only",
    "sign in to read",
    "create an account to continue",
    "free trial",
    "unlock this article",
    "paywall",
    "subscriber-only",
    "paid content",
    "register to continue reading",
    "already a subscriber",
    "become a member",
]

# Domain classification keywords
DOMAIN_KEYWORDS = {
    "Astronomy": [
        "space", "planet", "star", "galaxy", "moon", "mars", "nasa", "asteroid",
        "comet", "telescope", "orbit", "solar", "cosmic", "universe", "black hole",
        "supernova", "nebula", "spacecraft", "rocket", "satellite", "exoplanet",
        "astronomy", "astronaut", "celestial", "meteor", "jupiter", "saturn",
        "venus", "mercury", "neptune", "uranus", "milky way", "hubble", "webb",
        "iss", "international space station", "launch", "mission", "lunar"
    ],
    "Wildlife": [
        "animal", "wildlife", "species", "mammal", "bird", "fish", "reptile",
        "amphibian", "insect", "predator", "prey", "endangered", "extinction",
        "conservation", "habitat", "zoo", "safari", "migration", "behavior",
        "wolf", "bear", "lion", "tiger", "elephant", "whale", "dolphin", "shark",
        "eagle", "owl", "snake", "frog", "butterfly", "bee", "ant", "spider",
        "primate", "ape", "monkey", "gorilla", "chimpanzee", "orangutan",
        "ocean life", "marine life", "coral reef", "rainforest", "savanna",
        "arctic animal", "polar bear", "penguin", "seal", "otter", "deer",
        "fox", "rabbit", "squirrel", "bat", "crocodile", "turtle", "parrot"
    ],
    "Biology": [
        "cell", "dna", "gene", "evolution", "fossil", "dinosaur", "bacteria",
        "virus", "protein", "organism", "genetics", "mutation", "enzyme",
        "microbe", "biology", "life form", "reproduction", "anatomy", "brain",
        "neuron", "disease", "infection", "immune", "plant", "fungus",
        "ecosystem", "biodiversity", "molecular", "genome", "chromosome",
        "stem cell", "cancer", "antibiotic", "vaccine", "pathogen", "parasite"
    ],
    "Climate": [
        "climate", "weather", "temperature", "warming", "carbon", "emission",
        "greenhouse", "ice", "glacier", "arctic", "antarctic", "sea level",
        "drought", "flood", "hurricane", "storm", "atmosphere", "pollution",
        "renewable", "energy", "fossil fuel", "ocean warming", "heat wave",
        "wildfire", "deforestation", "methane", "ozone", "el nino", "la nina",
        "precipitation", "rainfall", "snowfall", "permafrost", "ecosystem change",
        "environmental", "sustainability", "earth", "global"
    ]
}

# FREE, open access URLs organized by domain
# These sources provide full articles without paywalls
DOMAIN_URLS = {
    "Wildlife": [
        # Live Science Animals - wildlife coverage
        "https://www.livescience.com/animals",
    ],
    "Climate": [
        # Inside Climate News - dedicated climate journalism
        "https://insideclimatenews.org/",
    ]
}


def fetch_nasa_apod():
    """Fetch NASA Astronomy Picture of the Day."""
    try:
        params = {"api_key": NASA_API_KEY}
        response = requests.get(NASA_APOD_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "title": data.get("title", "NASA Image of the Day"),
            "explanation": data.get("explanation", "")[:300] + "..." if len(data.get("explanation", "")) > 300 else data.get("explanation", ""),
            "url": data.get("hdurl") or data.get("url", ""),
            "media_type": data.get("media_type", "image"),  # 'image' or 'video'
            "date": data.get("date", ""),
            "copyright": data.get("copyright", "NASA"),
        }
    except Exception as e:
        print(f"    Warning: Could not fetch NASA APOD: {e}")
        # Return a fallback NASA image when API is rate limited
        print("    Using fallback NASA image...")
        return {
            "title": "The Milky Way Over Monument Valley",
            "explanation": "The Milky Way arches over the iconic buttes of Monument Valley in this stunning night sky view. Our galaxy contains over 200 billion stars, and on clear nights away from light pollution, we can see the band of light created by billions of distant stars in our galactic disk.",
            "url": "https://apod.nasa.gov/apod/image/2401/MwskyMV_Schweitzer_1080.jpg",
            "media_type": "image",
            "copyright": "NASA/APOD"
        }


def fetch_nature_feeds():
    """Fetch nature/science RSS feed items with images from various sources."""
    items = []

    for feed_url in NATURE_RSS_FEEDS:
        try:
            response = requests.get(feed_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "xml")

            # Determine source for badge
            if "smithsonian" in feed_url:
                source = "Smithsonian"
            elif "bbc" in feed_url:
                source = "BBC Science"
            elif "sciam" in feed_url or "scientificamerican" in feed_url:
                source = "Scientific American"
            else:
                source = "Nature News"

            for item in soup.find_all("item")[:3]:  # Get top 3 from each feed
                title = item.find("title")
                link = item.find("link")
                description = item.find("description")

                # Try to find image in media:content or enclosure
                image_url = None

                # Check media:content (most common for images)
                media = item.find("media:content")
                if media and media.get("url"):
                    image_url = media.get("url")

                # Check media:thumbnail
                if not image_url:
                    media = item.find("media:thumbnail")
                    if media and media.get("url"):
                        image_url = media.get("url")

                # Check enclosure
                if not image_url:
                    enclosure = item.find("enclosure")
                    if enclosure and enclosure.get("url"):
                        enc_type = enclosure.get("type", "")
                        if "image" in enc_type or enc_type == "":
                            image_url = enclosure.get("url")

                # Try to extract image from description HTML
                if not image_url and description:
                    desc_text = description.get_text() if hasattr(description, 'get_text') else str(description.string or "")
                    desc_soup = BeautifulSoup(desc_text, "html.parser")
                    img = desc_soup.find("img")
                    if img and img.get("src"):
                        image_url = img.get("src")

                # Get link text (handle both text and CDATA)
                link_url = ""
                if link:
                    link_url = link.get_text(strip=True) if hasattr(link, 'get_text') else str(link.string or "")

                if title:
                    title_text = title.get_text(strip=True) if hasattr(title, 'get_text') else str(title.string or "")
                    desc_text = ""
                    if description:
                        desc_text = description.get_text(strip=True) if hasattr(description, 'get_text') else str(description.string or "")

                    items.append({
                        "title": title_text,
                        "url": link_url,
                        "image": image_url,
                        "description": desc_text[:150] + "..." if len(desc_text) > 150 else desc_text,
                        "source": source,
                    })

        except Exception as e:
            print(f"    Warning: Could not fetch feed {feed_url}: {e}")
            continue

    # Remove duplicates based on title, prioritize items with images
    seen_titles = set()
    unique_items = []
    items_with_images = [i for i in items if i.get("image")]
    items_without_images = [i for i in items if not i.get("image")]

    for item in items_with_images + items_without_images:
        if item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            unique_items.append(item)

    return unique_items[:4]


def is_paywalled_url(url):
    """Check if a URL is from a known paywalled domain."""
    url_lower = url.lower()
    for domain in PAYWALLED_DOMAINS:
        if domain in url_lower:
            return True
    return False


def check_for_paywall(soup, url):
    """Check if page content indicates a paywall."""
    # First check URL
    if is_paywalled_url(url):
        return True

    # Check page text for paywall indicators
    page_text = soup.get_text().lower()
    for indicator in PAYWALL_INDICATORS:
        if indicator in page_text:
            # Look for paywall elements near the indicator
            paywall_elements = soup.select('[class*="paywall"], [class*="subscribe"], [class*="premium"], [id*="paywall"]')
            if paywall_elements:
                return True

    # Check for common paywall class names
    paywall_selectors = [
        '[class*="paywall"]',
        '[class*="subscriber-only"]',
        '[class*="premium-content"]',
        '[class*="locked-content"]',
        '[data-paywall]',
        '.subscription-required',
    ]

    for selector in paywall_selectors:
        if soup.select(selector):
            return True

    return False


def classify_domain(title, summary):
    """Classify an article into a scientific domain based on keywords."""
    text = (title + " " + summary).lower()

    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        scores[domain] = score

    # Return domain with highest score, or None if no matches
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return None


def normalize_characters(text):
    """Convert special characters to HTML entities to avoid encoding issues."""
    if not text:
        return text

    # STEP 1: Fix mojibake patterns using Unicode escapes (safe for any encoding)
    # These are UTF-8 bytes misinterpreted as Latin-1/Windows-1252
    mojibake_patterns = [
        ("\u00e2\u0080\u0099", "&#39;"),  # â€™ -> '
        ("\u00e2\u0080\u0098", "&#39;"),  # â€˜ -> '
        ("\u00e2\u0080\u009c", "&quot;"), # â€œ -> "
        ("\u00e2\u0080\u009d", "&quot;"), # â€ -> "
        ("\u00e2\u0080\u0093", "-"),      # â€" -> -
        ("\u00e2\u0080\u0094", "-"),      # â€" -> -
        ("\u00e2\u0080\u00a6", "..."),    # â€¦ -> ...
        ("\u00c2\u00a0", " "),            # Â  -> space
    ]

    for bad, good in mojibake_patterns:
        text = text.replace(bad, good)

    # STEP 2: Use regex to catch remaining corrupted patterns
    # The â character (U+00E2) followed by special bytes
    text = re.sub(r'\u00e2\u0080.', "&#39;", text)
    text = re.sub(r'\u00e2.', "&#39;", text)
    # Euro sign followed by space and letter (corrupted apostrophe)
    text = re.sub(r'\u20ac\s*(?=\w)', "&#39;", text)
    text = re.sub(r"'\u20ac\s*", "&#39;", text)

    # STEP 3: Convert Unicode smart quotes to HTML entities
    unicode_map = {
        '\u2018': "&#39;",   # Left single quote '
        '\u2019': "&#39;",   # Right single quote '
        '\u201C': "&quot;",  # Left double quote "
        '\u201D': "&quot;",  # Right double quote "
        '\u2032': "&#39;",   # Prime
        '\u2033': "&quot;",  # Double prime
        '\u0060': "&#39;",   # Grave accent
        '\u00B4': "&#39;",   # Acute accent
        '\u2013': "-",       # En dash
        '\u2014': "-",       # Em dash
        '\u2015': "-",       # Horizontal bar
        '\u2012': "-",       # Figure dash
        '\u00A0': " ",       # Non-breaking space
        '\u2026': "...",     # Ellipsis
        '\u00AB': "&quot;",  # Left guillemet
        '\u00BB': "&quot;",  # Right guillemet
        '\u201A': "&#39;",   # Single low quote
        '\u201E': "&quot;",  # Double low quote
        '\u00e2': "&#39;",   # Standalone â (from corruption)
    }

    for char, replacement in unicode_map.items():
        text = text.replace(char, replacement)

    # STEP 4: Final cleanup with regex for any remaining special quotes
    text = re.sub(r'[\u2018\u2019\u201a\u201b]', "&#39;", text)
    text = re.sub(r'[\u201c\u201d\u201e\u201f]', "&quot;", text)

    return text


def fix_spacing_and_grammar(text):
    """Fix common spacing issues and remove UI artifacts from scraped text."""
    if not text:
        return text

    # Remove common UI navigation text that gets scraped
    ui_patterns = [
        r'Previous\s*image\s*Next\s*image',
        r'Next\s*image\s*Previous\s*image',
        r'Previous\s*image',
        r'Next\s*image',
        r'Share\s*on\s*(Facebook|Twitter|LinkedIn|Email)',
        r'Share\s*this\s*article',
        r'Read\s*more:?',
        r'See\s*also:?',
        r'Related:?',
        r'Advertisement',
        r'Sponsored\s*content',
        r'Click\s*to\s*expand',
        r'Show\s*caption',
        r'Hide\s*caption',
        r'Image\s*\d+\s*of\s*\d+',
        r'Photo\s*by:?',
        r'Credit:',
        r'Photograph:',
        r'\[.*?\]',  # Remove bracketed text like [Image], [Video]
    ]
    for pattern in ui_patterns:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)

    # Fix numbers followed by letters (e.g., "1,000mountain" -> "1,000 mountain")
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)

    # Fix letters followed by numbers with no space (e.g., "over1,000" -> "over 1,000")
    text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)

    # Fix missing space after periods before capital letters
    text = re.sub(r'\.([A-Z])', r'. \1', text)

    # Fix missing space after other punctuation before capital letters
    text = re.sub(r',([A-Z])', r', \1', text)
    text = re.sub(r':([A-Z])', r': \1', text)
    text = re.sub(r';([A-Z])', r'; \1', text)

    # Fix camelCase-like concatenations (lowercase followed by uppercase)
    text = re.sub(r'([a-z])([A-Z][a-z]{2,})', r'\1 \2', text)

    # Fix specific word concatenations (safe patterns that won't break real words)
    # Format: pattern -> replacement
    word_fixes = [
        # Common verb concatenations
        (r'\b(\w{3,}s)(published|released|reported|discovered|revealed|found|shows?|left|right)\b', r'\1 \2'),
        # Article + word (only specific safe cases)
        (r'\bastatement\b', 'a statement'),
        (r'\banother\b', 'another'),  # Don't break this
        (r'\babout\b', 'about'),  # Don't break this
        # Preposition concatenations (specific patterns)
        (r'\bofthe\b', 'of the'),
        (r'\binthe\b', 'in the'),
        (r'\btothe\b', 'to the'),
        (r'\bforthe\b', 'for the'),
        (r'\bandthe\b', 'and the'),
        (r'\bonthe\b', 'on the'),
        (r'\batthe\b', 'at the'),
        (r'\bbythe\b', 'by the'),
        (r'\bfromthe\b', 'from the'),
        (r'\bwiththe\b', 'with the'),
        (r'\bthatthe\b', 'that the'),
        (r'\bisthe\b', 'is the'),
        (r'\basthe\b', 'as the'),
        (r'\bwasthe\b', 'was the'),
        (r'\barethe\b', 'are the'),
        (r'\bwerethe\b', 'were the'),
        # Other common concatenations
        (r'\bauthorsdiscuss', 'authors discuss'),
        (r'\bresearchersfound', 'researchers found'),
        (r'\bscientistsdiscovered', 'scientists discovered'),
        (r'\bstudyshows', 'study shows'),
        (r'\bresultsshow', 'results show'),
        (r'\bdatashows', 'data shows'),
        (r'\bfindingsshow', 'findings show'),
        (r'\bteamfound', 'team found'),
        (r'\baccordingto', 'according to'),
    ]
    for pattern, replacement in word_fixes:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Fix "in" followed by scientific names (e.g., "inC. elegans" -> "in C. elegans")
    text = re.sub(r'\bin([A-Z]\.)', r'in \1', text)

    # Fix spacing around hyphens that got lost
    text = re.sub(r'(\w)-([A-Z])', r'\1 - \2', text)

    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Clean up spaces before punctuation
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)

    # Ensure space after punctuation (except for abbreviations)
    text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)

    # Fix double punctuation
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',{2,}', ',', text)

    return text.strip()


def simplify_text(text):
    """Simplify text to approximately 7th grade reading level."""
    # First normalize special characters
    text = normalize_characters(text)

    # Fix spacing issues and remove UI artifacts
    text = fix_spacing_and_grammar(text)

    # Remove complex punctuation and clean up
    text = re.sub(r'\s+', ' ', text).strip()

    # Simple word replacements for common scientific terms
    replacements = {
        "approximately": "about",
        "utilize": "use",
        "demonstrate": "show",
        "investigate": "study",
        "significant": "important",
        "subsequently": "then",
        "preliminary": "early",
        "hypothesis": "idea",
        "methodology": "method",
        "phenomenon": "event",
        "unprecedented": "never seen before",
        "substantial": "large",
        "consequently": "so",
        "furthermore": "also",
        "nevertheless": "but",
        "comprehensive": "complete",
        "fundamental": "basic",
        "facilitate": "help",
        "implement": "use",
        "indicate": "show",
        "sufficient": "enough",
        "obtain": "get",
        "require": "need",
        "maintain": "keep",
        "establish": "set up",
        "additional": "more",
        "numerous": "many",
        "attempt": "try",
        "commence": "start",
        "terminate": "end",
        "endeavor": "try",
        "ascertain": "find out",
        "constitute": "make up",
        "regarding": "about",
        "prior to": "before",
        "in addition to": "besides",
        "in order to": "to",
        "due to the fact that": "because",
        "at this point in time": "now",
        "in the event that": "if",
    }

    for complex_word, simple_word in replacements.items():
        pattern = re.compile(re.escape(complex_word), re.IGNORECASE)
        text = pattern.sub(simple_word, text)

    return text


def fetch_article_content(url):
    """Fetch the main content and image from an article page, checking for paywalls."""
    # Skip known paywalled domains
    if is_paywalled_url(url):
        return {"content": "", "image": None}

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Check for paywall
        if check_for_paywall(soup, url):
            return {"content": "", "image": None}

        # Extract article image
        image_url = extract_article_image(soup, url)

        # Remove unwanted elements for content extraction
        for elem in soup.select("script, style, nav, header, footer, aside, .ad, .advertisement"):
            elem.decompose()

        # Try to find main article content
        content = ""

        # Common article content selectors
        selectors = [
            "article p",
            ".article-body p",
            ".post-content p",
            ".entry-content p",
            ".story-body p",
            ".article-content p",
            "#text p",  # ScienceDaily
            ".article__body p",
            "main p",
            ".content p"
        ]

        for selector in selectors:
            paragraphs = soup.select(selector)
            if paragraphs:
                # Get more paragraphs for better content extraction
                content = " ".join(p.get_text(strip=True) for p in paragraphs[:8])
                if len(content) > 300:
                    break

        # Fallback: get any paragraphs
        if len(content) < 300:
            paragraphs = soup.find_all("p")
            # Filter out very short paragraphs (likely navigation/ads)
            good_paragraphs = [p for p in paragraphs if len(p.get_text(strip=True)) > 50]
            content = " ".join(p.get_text(strip=True) for p in good_paragraphs[:8])

        # Clean up spacing issues from scraped content
        content = fix_spacing_and_grammar(content)

        return {"content": content[:2500], "image": image_url}

    except Exception:
        return {"content": "", "image": None}


def extract_article_image(soup, url):
    """Extract the main image from an article page."""
    image_url = None

    # Try Open Graph image first (most reliable for article thumbnails)
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        image_url = og_image.get("content")
        if image_url and not image_url.startswith("http"):
            image_url = None  # Skip relative URLs for og:image

    # Try Twitter card image
    if not image_url:
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            image_url = twitter_image.get("content")

    # Try schema.org image
    if not image_url:
        schema_image = soup.find("meta", attrs={"itemprop": "image"})
        if schema_image and schema_image.get("content"):
            image_url = schema_image.get("content")

    # Try common article image selectors
    if not image_url:
        image_selectors = [
            "article img",
            ".article-image img",
            ".featured-image img",
            ".post-thumbnail img",
            ".entry-image img",
            "#leadimage img",  # ScienceDaily
            ".lead-image img",
            "figure img",
            ".hero-image img",
            "main img",
        ]
        for selector in image_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if src and len(src) > 10:
                    # Skip tiny icons and tracking pixels
                    if not any(skip in src.lower() for skip in ["icon", "logo", "avatar", "1x1", "pixel"]):
                        image_url = src
                        break

    # Make relative URLs absolute
    if image_url and not image_url.startswith("http"):
        base = get_base_url(url)
        if base:
            image_url = base + image_url if image_url.startswith("/") else base + "/" + image_url

    return image_url


def extract_key_statistic(content, title):
    """Extract an interesting statistic or number from the article content."""
    if not content:
        return None

    text = content + " " + title

    # Patterns for interesting statistics (number + context)
    stat_patterns = [
        # Percentages
        r'(\d+(?:\.\d+)?)\s*(?:percent|%)\s+(?:of\s+)?([a-zA-Z\s]{5,40})',
        # Times/multiples
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:times?|x)\s+(?:more\s+|less\s+|faster\s+|slower\s+)?([a-zA-Z\s]{3,30})',
        # Large numbers with units
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|trillion|thousand)\s+([a-zA-Z\s]{3,30})',
        # Years/age
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:year|million year|billion year)s?\s+(?:old|ago)',
        # Distance/size with units
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(light[- ]?years?|miles?|kilometers?|km|meters?|feet)\s+(?:away|from|across|wide|long)',
        # Temperature
        r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:degrees?|°)\s*(?:Celsius|Fahrenheit|C|F)',
        # Species/discoveries count
        r'(?:more than\s+|over\s+|about\s+)?(\d+(?:,\d{3})*)\s+(?:new\s+)?(?:species|discoveries|stars?|planets?|galaxies)',
    ]

    for pattern in stat_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            full_match = match.group(0).strip()
            # Clean up and format
            full_match = re.sub(r'\s+', ' ', full_match)
            if len(full_match) < 60:  # Keep it concise
                return full_match

    # Fallback: find any sentence with a notable number
    sentences = re.split(r'[.!?]', text)
    for sent in sentences:
        # Look for sentences with large numbers or percentages
        if re.search(r'\b\d{2,}(?:,\d{3})*\b', sent) or re.search(r'\d+\s*%', sent):
            sent = sent.strip()
            if 20 < len(sent) < 80:
                return sent

    return None


def calculate_reading_time(content):
    """Calculate estimated reading time in minutes."""
    if not content:
        return 1

    # Average reading speed is about 200-250 words per minute
    word_count = len(content.split())
    minutes = max(1, round(word_count / 200))

    return minutes


def is_similar_to_title(sentence, title):
    """Check if a sentence is too similar to the title (likely a repetition)."""
    sent_words = set(re.findall(r'\b\w{4,}\b', sentence.lower()))
    title_words = set(re.findall(r'\b\w{4,}\b', title.lower()))

    if not sent_words or not title_words:
        return False

    overlap = len(sent_words & title_words)
    similarity = overlap / min(len(sent_words), len(title_words))

    return similarity > 0.6


def remove_quotes(text):
    """Remove direct quotes and attribution phrases from text."""
    # Remove text inside various quote styles (complete quoted sections)
    text = re.sub(r'"[^"]{5,300}"', '', text)  # Regular quotes
    text = re.sub(r'"[^"]{5,300}"', '', text)  # Smart quotes

    # Remove common attribution phrases
    text = re.sub(r',?\s*said\s+[\w\s\.]+$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',?\s*says\s+[\w\s\.]+$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',?\s*according to\s+[\w\s\.]+$', '', text, flags=re.IGNORECASE)

    # Clean up extra whitespace and punctuation
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*,\s*,+', ',', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'^\s*[,;:\s]+', '', text)
    text = re.sub(r'[,;:\s]+$', '', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)

    return text.strip()


def fix_punctuation(sentence):
    """Fix common punctuation and grammar issues in a sentence."""
    if not sentence:
        return ""

    sentence = sentence.strip()

    # Remove leading punctuation
    sentence = re.sub(r'^[,;:\s]+', '', sentence)

    # Fix common abbreviations
    sentence = re.sub(r'\bU\.\s*S\.', 'U.S.', sentence)

    # Capitalize first letter
    if sentence and sentence[0].islower():
        sentence = sentence[0].upper() + sentence[1:]

    # Fix spacing around punctuation
    sentence = re.sub(r'\s+([.,;:!?])', r'\1', sentence)
    sentence = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', sentence)

    # Fix multiple periods and spaces
    sentence = re.sub(r'\.{2,}', '.', sentence)
    sentence = re.sub(r'\s+', ' ', sentence)

    # Ensure sentence ends with proper punctuation
    sentence = sentence.strip()
    if sentence and sentence[-1] not in '.!?':
        sentence += '.'

    # Fix bad endings
    sentence = re.sub(r',\.$', '.', sentence)

    return sentence.strip()


def generate_simple_explanation(title, summary, full_content=""):
    """Generate 2-3 clear bullet points explaining the article at 7th grade level."""

    # Combine all available text
    all_text = f"{summary} {full_content}".strip()

    # Apply simplifications
    all_text = simplify_text(all_text)

    # Split into sentences - use a simple split that preserves sentence boundaries
    sentences = []
    for part in re.split(r'(?<=[.!?])\s+(?=[A-Z])', all_text):
        part = part.strip()
        if len(part) > 50:
            sentences.append(part)

    # Remove sentences similar to title
    title_simplified = simplify_text(title)
    filtered = []
    for sent in sentences:
        if not is_similar_to_title(sent, title_simplified):
            filtered.append(sent)
    sentences = filtered

    # Clean up sentences - remove quotes, names, organizations, dates
    clean_sentences = []
    for sent in sentences:
        # Remove quoted text (various quote styles)
        sent = re.sub(r'"[^"]*"', '', sent)
        sent = re.sub(r'"[^"]*"', '', sent)
        sent = re.sub(r'"[^"]*$', '', sent)

        # Remove scientist names and titles
        sent = re.sub(r'\b(Dr\.|Prof\.|Professor)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?', 'researchers', sent)
        sent = re.sub(r'\b[A-Z][a-z]+\s+(and\s+)?(colleagues|co-authors|team)', 'researchers', sent)
        sent = re.sub(r'\b[A-Z][a-z]+\s+(explains?|notes?|says?|adds?)\b', 'Researchers say', sent)

        # Remove single researcher names before verbs (e.g., "Lin shared", "Hansen noted")
        sent = re.sub(r'\b[A-Z][a-z]{2,15}\s+(shared|presented|described|reported|argued|proposed|suggested|published|found|showed)\b', 'Researchers \\1', sent)
        sent = re.sub(r'\b[A-Z][a-z]{2,15}\s+and\s+(his|her|their)\s+', 'Researchers and their ', sent)

        # Remove partial names before common words (e.g., "Subo researchers")
        sent = re.sub(r'\b[A-Z][a-z]{2,10}\s+(researchers|scientists|team)\b', '\\1', sent)

        # Remove specific researcher names (capitalized words followed by common patterns)
        sent = re.sub(r',?\s*[A-Z][a-z]+\s+[A-Z][a-z]+,?\s*(a |the )?(lead |co-)?author[^,\.]*[,\.]?', '', sent)
        sent = re.sub(r'\b(lead |co-)?author\s+[A-Z][a-z]+\s+[A-Z][a-z]+', 'researchers', sent)

        # Remove organization names
        sent = re.sub(r'\b(University|Institute|College|Center|Centre)\s+of\s+[A-Z][\w\s,]+', 'a research institution', sent)
        sent = re.sub(r'\b[A-Z][a-z]+\s+(University|Institute|College|State)\b', 'a research institution', sent)
        sent = re.sub(r'\bETH\s+Zurich\b', 'researchers', sent)
        sent = re.sub(r'\b(NASA|NOAA|NSF|NIH|ESA)\b', 'scientists', sent)
        sent = re.sub(r'\b(Swiss Federal Institute|National Research Council)[^,\.]*', 'a research institution', sent)
        sent = re.sub(r'\bVrije Universiteit\s+\w+', 'a research institution', sent)

        # Remove parenthetical abbreviations like (WSL), (MIT), (UCLA)
        sent = re.sub(r'\s*\([A-Z]{2,6}\)', '', sent)

        # Remove conference/meeting names
        sent = re.sub(r"\bAGU's?\s+\d{4}\s+Annual\s+Meeting[^,\.]*", '', sent)
        sent = re.sub(r'\bat\s+AGU\d*\b', '', sent)
        sent = re.sub(r'\bin\s+[A-Z][a-z]+,?\s+[A-Z][a-z]+\s*$', '', sent)  # "in New Orleans, Louisiana"

        # Remove journal names and publication info
        sent = re.sub(r'\b(published|appears?|reported)\s+(in|on)\s+(the\s+)?(AGU\s+)?journal\s+[A-Z][\w\s]+', 'published', sent)
        sent = re.sub(r'\bin\s+the\s+(AGU\s+)?journal\s+[A-Z][\w\s&]+', '', sent)
        sent = re.sub(r'\bthe\s+AGU\s+journal\s+[A-Z][\w\s]+', '', sent)
        sent = re.sub(r'\b(Science|Nature|PNAS|Cell)\s+(Advances|Communications|Reports)?', 'a scientific journal', sent)
        sent = re.sub(r'\bGeophysical Research Letters\b', '', sent)

        # Remove dates
        sent = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', '', sent)
        sent = re.sub(r'\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', '', sent)
        sent = re.sub(r'\b\d{4}\s+(study|research|paper|report)', 'new research', sent)
        sent = re.sub(r'\bDecember\s+\d+\s+at\s+AGU\d+', '', sent)
        sent = re.sub(r'\bIn\s+\d{4},\s*', '', sent)  # "In 2014, ..."
        sent = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b', '', sent)  # Just month + day
        sent = re.sub(r'\bpublished\s+(on\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', 'published', sent)

        # Remove journal names - more comprehensive
        sent = re.sub(r'\bin\s+the\s+Proceedings\s+of\s+[^,\.]+', '', sent)
        sent = re.sub(r'\bProceedings\s+of\s+the\s+National\s+Academy\s+of\s+Sciences\b', '', sent)
        sent = re.sub(r'\(cf\.[^)]+\)', '', sent)  # Remove "(cf.Journal Name)"
        sent = re.sub(r'\bcf\.\s*[A-Z][a-zA-Z\s]+', '', sent)  # Remove "cf. Journal Name"

        # Remove astronomical catalog names
        sent = re.sub(r'\bRM\s+J[\d\.\+]+', 'the cluster', sent)
        sent = re.sub(r'\b[A-Z]{1,3}\s+J?\d{4,}[\d\.\+\-]+', 'the object', sent)

        # Remove "ETH" before researchers
        sent = re.sub(r'\bETH\s+researchers\b', 'researchers', sent)
        sent = re.sub(r'\bthe\s+researchers-led\s+team\b', 'the research team', sent)

        # Remove section headers that appear mid-sentence
        sent = re.sub(r'\b[A-Z][a-z]+(\s+[A-Z][a-z]+){1,4}\s+(?=[A-Z][a-z]+\s+(study|research|team|scientists|researchers|found|shows?))', '', sent)
        sent = re.sub(r'^[A-Z][a-z]+(\s+[a-z]+){0,3}\s+[A-Z]', lambda m: m.group(0) if len(m.group(0)) > 50 else '', sent)
        # Remove section headers followed by "The" (common pattern)
        sent = re.sub(r'^[A-Z][a-z]+(\s+[a-z]+){0,6}\s+The\s+', 'The ', sent)

        # Remove attribution phrases
        sent = re.sub(r',?\s*(said|says|noted|added|explained)\s+[\w\s\.,]+$', '', sent, flags=re.IGNORECASE)
        sent = re.sub(r',?\s*(according to|led by)\s+[\w\s\.,]+$', '', sent, flags=re.IGNORECASE)

        # Clean up whitespace and punctuation
        sent = re.sub(r'\s+', ' ', sent).strip()
        sent = re.sub(r':the\b', ': the', sent)
        sent = re.sub(r'\s*:\s*$', '.', sent)
        sent = re.sub(r'\s+\.', '.', sent)
        sent = re.sub(r'\.{2,}', '.', sent)
        sent = re.sub(r',\s*,', ',', sent)
        sent = re.sub(r'^\s*,\s*', '', sent)
        sent = re.sub(r',\s*\.', '.', sent)

        # Replace awkward phrases from removals
        sent = re.sub(r'\bresearchers researchers\b', 'researchers', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bthe the\b', 'the', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\ba a\b', 'a', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bin the a research institution\b', 'at a research institution', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bthe Swiss a research institution\b', 'a Swiss research institution', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bthe a research institution\b', 'a research institution', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bled by researchers,\s*a research institution[^,\.]*,?\s*(and\s+)?a research institution[^,\.]*', 'led by researchers at various institutions', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bled by researchers,\s*a research institution[^,\.]*', 'led by researchers', sent, flags=re.IGNORECASE)
        sent = re.sub(r'\bResearchers and their colleagues\b', 'Researchers', sent)
        sent = re.sub(r'\bresearchers and their colleagues\b', 'researchers', sent)
        sent = re.sub(r',\s*and\s*,', ' and', sent)
        sent = re.sub(r'\bat\s*,', 'in', sent)  # Fix "at , Louisiana"
        sent = re.sub(r'\bresearch\s*,\s*Category', 'proposed a Category', sent)  # Fix broken Category sentence
        sent = re.sub(r'\s+', ' ', sent).strip()

        # Skip if too short after cleaning
        if len(sent) < 60:
            continue

        # Skip sentences starting with lowercase, quotes, or parentheses
        if sent and (sent[0].islower() or sent[0] in '"("'):
            continue

        # Skip sentences that look like section headers
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,5}\s*$', sent):
            continue

        # Skip sentences that appear incomplete (broken by text removal)
        incomplete_patterns = [
            r'\b(describe|describes|described)\s+as\s+(being\s+)?(in\s+)?a\s*$',
            r'\bbecome\s+what\s+scientists\s+describe\s+as\s+That\b',
            r'\bIn\s+this\s+context,\s*$',
            r'\b(say|says)\s+that\s*$',
            r'\bResearchers\s+say\.\s+As\b',
            r'\bWe\s+picked\b',  # Quotes that weren't fully removed
            r'\bResearchers\s+say\s+that\s+this\s+narrow\b',  # Quote remnant
            r'\bpublished\s+on\s*\.\s*$',  # "published on ."
            r'\bA\s+study\s+published\s+on\s*\.',  # "A study published on ."
            r'\bthe\s+researchers\s+reported\.\s+Impossible\b',  # Broken by text removal
            r'\bin\s+Louisiana\s*\.$',  # "in Louisiana." as ending (location remnant)
            r'\bResearchers\s+shared\s+the\s+research\s+during\s+an\s+oral',  # Conference talk remnant
            r'^[A-Z][a-z]+(\s+[a-z]+){2,12}\s+The\s+',  # Section header followed by sentence (e.g., "Strategies to reduce... The scale...")
        ]
        skip_sent = False
        for pattern in incomplete_patterns:
            if re.search(pattern, sent, re.IGNORECASE):
                skip_sent = True
                break
        if skip_sent:
            continue

        # Ensure proper ending
        if sent and sent[-1] not in '.!?':
            sent += '.'

        # Capitalize first letter
        if sent and sent[0].islower():
            sent = sent[0].upper() + sent[1:]

        clean_sentences.append(sent)

    sentences = clean_sentences

    # Score sentences for relevance
    discovery_words = ["found", "discovered", "shows", "revealed", "study", "research",
                       "scientists", "researchers", "measured", "data", "results"]
    impact_words = ["could", "may", "might", "help", "important", "means",
                    "change", "future", "first", "new", "understand"]

    scored = []
    for sent in sentences:
        if len(sent) > 300:  # Skip very long sentences
            continue

        score = 0
        sent_lower = sent.lower()

        for word in discovery_words:
            if word in sent_lower:
                score += 2
        for word in impact_words:
            if word in sent_lower:
                score += 1
        if re.search(r'\d+', sent):  # Has numbers
            score += 1

        scored.append((score, sent))

    scored.sort(reverse=True, key=lambda x: x[0])

    # Select top 2-3 unique sentences
    bullet_points = []
    used_words = []

    for score, sent in scored:
        # Check for redundancy
        sent_words = set(sent.lower().split())
        is_redundant = False
        for prev_words in used_words:
            if len(sent_words & prev_words) > len(sent_words) * 0.5:
                is_redundant = True
                break

        if not is_redundant and score > 0:
            bullet_points.append(sent)
            used_words.append(sent_words)

        if len(bullet_points) >= 3:
            break

    # Fallback: use first good sentences if we don't have enough
    if len(bullet_points) < 2:
        for sent in sentences:
            if sent not in bullet_points:
                bullet_points.append(sent)
            if len(bullet_points) >= 2:
                break

    # Final fallback
    if not bullet_points:
        simple_summary = simplify_text(summary)
        if simple_summary and len(simple_summary) > 50:
            bullet_points.append(simple_summary)
        else:
            bullet_points.append("Scientists made new discoveries in this field of research.")

    # Build HTML bullet list with final spacing cleanup
    html_parts = ['<ul class="summary-bullets">']
    for point in bullet_points[:3]:
        # Apply final spacing fix to catch any remaining issues
        point = fix_spacing_and_grammar(point)
        html_parts.append(f'<li>{point}</li>')
    html_parts.append('</ul>')

    return '\n'.join(html_parts)


def get_base_url(url):
    """Extract base URL for building full links."""
    if "sciencedaily.com" in url:
        return "https://www.sciencedaily.com"
    elif "phys.org" in url:
        return "https://phys.org"
    elif "eurekalert.org" in url:
        return "https://www.eurekalert.org"
    elif "space.com" in url:
        return "https://www.space.com"
    elif "livescience.com" in url:
        return "https://www.livescience.com"
    elif "nasa.gov" in url:
        return "https://www.nasa.gov"
    elif "noaa.gov" in url:
        return "https://www.noaa.gov"
    elif "quantamagazine.org" in url:
        return "https://www.quantamagazine.org"
    elif "theconversation.com" in url:
        return "https://theconversation.com"
    elif "arstechnica.com" in url:
        return "https://arstechnica.com"
    elif "inverse.com" in url:
        return "https://www.inverse.com"
    elif "news.mit.edu" in url:
        return "https://news.mit.edu"
    elif "cosmosmagazine.com" in url:
        return "https://cosmosmagazine.com"
    elif "iflscience.com" in url:
        return "https://www.iflscience.com"
    elif "mongabay.com" in url:
        return "https://news.mongabay.com"
    elif "bbc.com" in url:
        return "https://www.bbc.com"
    elif "zmescience.com" in url:
        return "https://www.zmescience.com"
    elif "smithsonianmag.com" in url:
        return "https://www.smithsonianmag.com"
    elif "nationalzoo.si.edu" in url:
        return "https://nationalzoo.si.edu"
    elif "nationalgeographic.com" in url:
        return "https://www.nationalgeographic.com"
    elif "insideclimatenews.org" in url:
        return "https://insideclimatenews.org"
    return ""


def get_source_name(url):
    """Get display name for a source URL."""
    if "quantamagazine" in url:
        return "Quanta"
    elif "theconversation" in url:
        return "The Conversation"
    elif "arstechnica" in url:
        return "Ars Technica"
    elif "inverse.com" in url:
        return "Inverse"
    elif "news.mit.edu" in url:
        return "MIT News"
    elif "cosmosmagazine" in url:
        return "Cosmos"
    elif "iflscience" in url:
        return "IFLScience"
    elif "mongabay" in url:
        return "Mongabay"
    elif "bbc.com" in url:
        return "BBC"
    elif "zmescience" in url:
        return "ZME Science"
    elif "smithsonianmag" in url:
        return "Smithsonian"
    elif "nationalzoo.si.edu" in url:
        return "Smithsonian Zoo"
    elif "nationalgeographic" in url:
        return "Nat Geo"
    elif "insideclimatenews" in url:
        return "Inside Climate News"
    elif "sciencedaily" in url:
        return "ScienceDaily"
    elif "phys.org" in url:
        return "Phys.org"
    elif "eurekalert" in url:
        return "EurekAlert"
    elif "space.com" in url:
        return "Space.com"
    elif "livescience" in url:
        return "Live Science"
    elif "nasa.gov" in url:
        return "NASA"
    elif "noaa.gov" in url:
        return "NOAA"
    return "Science News"


def fetch_domain_articles(domain, urls):
    """Fetch articles for a specific scientific domain from free sources only."""
    articles = []
    seen_titles = set()
    articles_per_source = {}  # Track count per source

    for url in urls:
        source_name = get_source_name(url)
        # Limit to 2 articles per source to ensure diversity
        if articles_per_source.get(source_name, 0) >= 2:
            continue
        # Stop if we have enough articles from enough sources
        if len(articles) >= 8 and len(articles_per_source) >= 2:
            break

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find article elements based on source
            if "quantamagazine" in url:
                article_elements = soup.select("a.card, article a, h2 a, h3 a, .post-title a")
            elif "theconversation" in url:
                article_elements = soup.select("article h2 a, .article-link, h3 a, .content-list a")
            elif "arstechnica" in url:
                article_elements = soup.select("article h2 a, .listing h2 a, h2 a[href*='/science/']")
            elif "inverse.com" in url:
                article_elements = soup.select("article a, h2 a, h3 a, .card a")
            elif "news.mit.edu" in url:
                article_elements = soup.select(".term-page--news-item a, article h3 a, .news-item a")
            elif "cosmosmagazine" in url:
                article_elements = soup.select("article a, h2 a, h3 a, .card-title a")
            elif "iflscience" in url:
                article_elements = soup.select("article a, h2 a, h3 a, .card a, .article-title a")
            elif "mongabay" in url:
                article_elements = soup.select("article h2 a, .post-title a, h3 a, .entry-title a")
            elif "bbc.com" in url:
                article_elements = soup.select("article h2 a, h3 a, .media__link, a.gs-c-promo-heading")
            elif "zmescience" in url:
                article_elements = soup.select("article h2 a, h3 a, .entry-title a, .post-title a")
            elif "smithsonianmag" in url:
                article_elements = soup.select("article h2 a, h3 a, .headline a, .article-title a")
            elif "nationalzoo.si.edu" in url:
                article_elements = soup.select("article h2 a, h3 a, .news-item a, .card a")
            elif "nationalgeographic.com" in url:
                article_elements = soup.select("article a, h2 a, h3 a, .PromoTile a, .GridPromoTile a, a[href*='/animals/']")
            elif "insideclimatenews.org" in url:
                # Select links to actual news articles (exclude category links)
                article_elements = soup.select("article h2 a, article h3 a, .entry-title a, a[href*='/news/2'], a[href*='/2026/'], a[href*='/2025/']")
            elif "sciencedaily" in url:
                article_elements = soup.select("#headlines a, .latest-head a, #featured a")
            elif "phys.org" in url:
                article_elements = soup.select("article h3 a, .news-item h3 a, article a[href*='/news/']")
            elif "eurekalert" in url:
                article_elements = soup.select(".release-item a, article a, .item a")
            elif "space.com" in url or "livescience" in url:
                article_elements = soup.select("article a, .listingResult a, .content a[href*='/']")
            elif "nasa.gov" in url:
                article_elements = soup.select(".hds-content-item a, article a, .card a")
            elif "noaa.gov" in url:
                article_elements = soup.select("article a, .news-item a, .card a")
            else:
                article_elements = soup.select("article a, h2 a, h3 a")

            for elem in article_elements[:15]:
                # Stop if we have enough articles from enough sources
                if len(articles) >= 8 and len(articles_per_source) >= 2:
                    break
                # Stop adding from this source if we hit the per-source limit
                if articles_per_source.get(source_name, 0) >= 2:
                    break

                try:
                    # Get headline
                    headline = elem.get_text(strip=True)
                    href = elem.get("href", "")

                    if not headline or len(headline) < 15 or headline in seen_titles:
                        continue

                    # Skip non-article items
                    skip_words = ["subscribe", "newsletter", "sign in", "menu", "search",
                                  "advertisement", "about us", "contact", "privacy"]
                    if any(skip in headline.lower() for skip in skip_words):
                        continue

                    # Skip category/tag pages (not actual articles)
                    if href and ("/category/" in href or "/tag/" in href or "/topics/" in href):
                        continue

                    # Build full URL
                    if href and not href.startswith("http"):
                        base = get_base_url(url)
                        if base:
                            href = base + href if href.startswith("/") else base + "/" + href

                    # Skip if URL is from paywalled domain
                    if is_paywalled_url(href):
                        continue

                    # Get summary from parent element if possible
                    summary = ""
                    parent = elem.find_parent(["article", "div", "li"])
                    if parent:
                        summary_el = parent.select_one("p, .summary, .excerpt, .description")
                        if summary_el:
                            summary = summary_el.get_text(strip=True)

                    if not summary:
                        summary = headline

                    # Verify this article belongs to this domain
                    # For Wildlife, be more lenient - animal-specific URLs should count
                    detected_domain = classify_domain(headline, summary)
                    if detected_domain != domain:
                        # Allow Wildlife articles that might be classified as Biology
                        if domain == "Wildlife" and detected_domain == "Biology":
                            # Check if it has any wildlife keywords
                            text_lower = (headline + " " + summary).lower()
                            wildlife_terms = ["animal", "species", "wildlife", "mammal", "bird",
                                            "fish", "predator", "prey", "endangered", "zoo",
                                            "wolf", "bear", "whale", "dolphin", "shark", "elephant"]
                            if any(term in text_lower for term in wildlife_terms):
                                pass  # Allow it
                            else:
                                continue
                        else:
                            continue

                    seen_titles.add(headline)

                    article_source = get_source_name(url)
                    articles.append({
                        "title": headline,
                        "summary": summary[:400] if len(summary) > 400 else summary,
                        "url": href or url,
                        "source": article_source,
                        "domain": domain
                    })
                    # Track articles per source
                    articles_per_source[article_source] = articles_per_source.get(article_source, 0) + 1

                except Exception:
                    continue

        except Exception as e:
            print(f"    Warning: Could not fetch {url}: {e}", file=sys.stderr)
            continue

    # Log source diversity
    if articles_per_source:
        sources = ", ".join(f"{k}:{v}" for k, v in articles_per_source.items())
        print(f"    Sources: {sources}")

    return articles


def enrich_with_explanations(articles):
    """Add simple explanations, images, stats, and reading time to articles."""
    enriched = []

    for article in articles:
        print(f"      Processing: {article['title'][:50]}...")

        # Skip paywalled URLs
        if is_paywalled_url(article.get("url", "")):
            print(f"        Skipping (paywalled source)")
            continue

        # Try to fetch full article content and image
        article_data = {"content": "", "image": None}
        if article.get("url"):
            article_data = fetch_article_content(article["url"])

        full_content = article_data.get("content", "")
        article_image = article_data.get("image")

        # If we got no content, the article might be paywalled
        if not full_content and article["summary"] == article["title"]:
            print(f"        Skipping (could not access content)")
            continue

        # Generate simple explanation
        explanation = generate_simple_explanation(
            article["title"],
            article["summary"],
            full_content
        )

        # Extract key statistic
        key_stat = extract_key_statistic(full_content, article["title"])

        # Calculate reading time
        read_time = calculate_reading_time(full_content)

        article["explanation"] = explanation
        article["image"] = article_image
        article["key_stat"] = key_stat
        article["read_time"] = read_time
        enriched.append(article)

    return enriched


def generate_html(domains_articles, featured_media=None):
    """Generate a clean, readable HTML page with tile/card-based layout."""
    # Use Mountain Time for display
    now_mt = datetime.now(MOUNTAIN_TZ)
    today = now_mt.strftime("%A, %B %d, %Y")
    update_time = now_mt.strftime("%I:%M %p") + " MT"

    # Default featured_media structure
    if featured_media is None:
        featured_media = {"nasa": None, "natgeo": []}

    domain_config = {
        "Wildlife": {"icon": "&#129421;", "class": "wildlife", "desc": "Animals & Nature", "color1": "#f57c00", "color2": "#ffb300"},
        "Climate": {"icon": "&#127758;", "class": "climate", "desc": "Weather & Environment", "color1": "#0575e6", "color2": "#00d4ff"},
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Science Digest - {today}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            color: #e8e8e8;
            line-height: 1.7;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 24px;
        }}

        header {{
            text-align: center;
            margin-bottom: 60px;
            padding-bottom: 40px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }}

        h1 {{
            font-size: 3.2em;
            font-weight: 300;
            letter-spacing: 8px;
            margin-bottom: 12px;
            background: linear-gradient(90deg, #00d4ff, #7b68ee, #ff6b9d);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .subtitle {{
            color: #8892b0;
            font-size: 1.1em;
            font-weight: 300;
            letter-spacing: 2px;
        }}

        .date {{
            color: #64ffda;
            font-size: 0.9em;
            margin-top: 20px;
            letter-spacing: 1px;
            font-weight: 500;
        }}

        .free-badge {{
            display: inline-block;
            margin-top: 16px;
            padding: 8px 20px;
            background: rgba(100, 255, 218, 0.1);
            border: 1px solid rgba(100, 255, 218, 0.3);
            border-radius: 30px;
            font-size: 0.75em;
            color: #64ffda;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}

        .domain-section {{
            margin-bottom: 50px;
        }}

        .domain-header {{
            display: flex;
            align-items: center;
            margin-bottom: 28px;
            padding-left: 8px;
        }}

        .domain-icon {{
            width: 56px;
            height: 56px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            font-size: 1.8em;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}

        .astronomy-icon {{
            background: linear-gradient(135deg, #4a00e0, #8e2de2);
        }}

        .wildlife-icon {{
            background: linear-gradient(135deg, #f57c00, #ffb300);
        }}

        .biology-icon {{
            background: linear-gradient(135deg, #11998e, #38ef7d);
        }}

        .climate-icon {{
            background: linear-gradient(135deg, #0575e6, #00d4ff);
        }}

        .domain-title-group h2 {{
            font-size: 1.6em;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 4px;
            letter-spacing: 0.5px;
        }}

        .domain-desc {{
            font-size: 0.9em;
            color: #8892b0;
            font-weight: 400;
        }}

        /* Card Grid Layout */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}

        .card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            text-decoration: none;
            color: inherit;
            cursor: pointer;
        }}

        .card-with-image {{
            padding: 0;
        }}

        .card:not(.card-with-image) {{
            padding: 28px;
        }}

        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #64ffda, #7b68ee);
            opacity: 0;
            transition: opacity 0.3s ease;
            z-index: 1;
        }}

        .card:hover {{
            transform: translateY(-8px);
            border-color: rgba(100, 255, 218, 0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.4), 0 0 40px rgba(100, 255, 218, 0.1);
            background: rgba(255,255,255,0.05);
        }}

        .card:hover::before {{
            opacity: 1;
        }}

        .card-image-wrapper {{
            width: 100%;
            height: 180px;
            overflow: hidden;
            position: relative;
        }}

        .card-image {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.4s ease;
        }}

        .card:hover .card-image {{
            transform: scale(1.05);
        }}

        .card-content {{
            padding: 24px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }}

        .card-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}

        .card-source {{
            font-size: 0.7em;
            color: #64ffda;
            background: rgba(100, 255, 218, 0.1);
            padding: 4px 12px;
            border-radius: 20px;
            display: inline-block;
            font-weight: 500;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        .card-read-time {{
            font-size: 0.7em;
            color: #8892b0;
            background: rgba(136, 146, 176, 0.15);
            padding: 4px 10px;
            border-radius: 15px;
            font-weight: 500;
        }}

        .card-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #ffffff;
            display: block;
            margin-bottom: 16px;
            line-height: 1.5;
            transition: color 0.3s ease;
        }}

        .card:hover .card-title {{
            color: #64ffda;
        }}

        .card-stat {{
            background: linear-gradient(135deg, rgba(123, 104, 238, 0.15), rgba(100, 255, 218, 0.1));
            border: 1px solid rgba(123, 104, 238, 0.3);
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }}

        .stat-icon {{
            font-size: 1.2em;
            flex-shrink: 0;
        }}

        .stat-text {{
            font-size: 0.85em;
            color: #ccd6f6;
            font-weight: 500;
            line-height: 1.4;
        }}

        .card-bullets {{
            list-style: none;
            flex-grow: 1;
        }}

        .card-bullets li {{
            position: relative;
            padding-left: 18px;
            margin-bottom: 14px;
            font-size: 0.88em;
            color: #a8b2d1;
            line-height: 1.6;
        }}

        .card-bullets li:last-child {{
            margin-bottom: 0;
        }}

        .card-bullets li::before {{
            content: "";
            position: absolute;
            left: 0;
            top: 9px;
            width: 6px;
            height: 6px;
            background: #64ffda;
            border-radius: 50%;
        }}

        .no-articles {{
            grid-column: 1 / -1;
            color: #8892b0;
            font-style: italic;
            text-align: center;
            padding: 60px 30px;
            background: rgba(255,255,255,0.02);
            border-radius: 20px;
            border: 1px dashed rgba(255,255,255,0.1);
        }}

        footer {{
            text-align: center;
            margin-top: 60px;
            padding-top: 40px;
            border-top: 1px solid rgba(255,255,255,0.08);
            color: #5a6a8a;
            font-size: 0.85em;
        }}

        .sources-list {{
            margin-top: 12px;
            font-size: 0.85em;
            color: #64ffda;
        }}

        .refresh-btn {{
            display: inline-block;
            margin-top: 24px;
            padding: 14px 36px;
            background: linear-gradient(135deg, #7b68ee, #00d4ff);
            color: white;
            text-decoration: none;
            border-radius: 30px;
            font-size: 0.85em;
            font-weight: 500;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            text-transform: uppercase;
        }}

        .refresh-btn:hover {{
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(123, 104, 238, 0.4);
        }}

        /* Featured Media Section */
        .featured-section {{
            margin-bottom: 60px;
        }}

        .featured-header {{
            display: flex;
            align-items: center;
            margin-bottom: 28px;
            padding-left: 8px;
        }}

        .featured-icon {{
            width: 56px;
            height: 56px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            font-size: 1.8em;
            background: linear-gradient(135deg, #ff6b6b, #feca57);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}

        .featured-title-group h2 {{
            font-size: 1.6em;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 4px;
        }}

        .featured-desc {{
            font-size: 0.9em;
            color: #8892b0;
        }}

        .featured-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
        }}

        .nasa-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
        }}

        .nasa-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(255, 107, 107, 0.3);
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }}

        .nasa-media {{
            width: 100%;
            height: 300px;
            object-fit: cover;
        }}

        .nasa-media-video {{
            width: 100%;
            height: 300px;
            border: none;
        }}

        .nasa-content {{
            padding: 24px;
        }}

        .nasa-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.7em;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }}

        .nasa-title {{
            font-size: 1.3em;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 12px;
            line-height: 1.4;
        }}

        .nasa-description {{
            font-size: 0.9em;
            color: #a8b2d1;
            line-height: 1.6;
        }}

        .nasa-credit {{
            margin-top: 12px;
            font-size: 0.75em;
            color: #5a6a8a;
        }}

        /* Stories Grid - Two tiles side by side */
        .stories-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}

        .story-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
            text-decoration: none;
            color: inherit;
            display: block;
        }}

        .story-card:hover {{
            transform: translateY(-6px);
            border-color: rgba(100, 255, 218, 0.3);
            box-shadow: 0 20px 50px rgba(0,0,0,0.4);
        }}

        .story-media {{
            width: 100%;
            height: 200px;
            object-fit: cover;
        }}

        .story-content {{
            padding: 20px;
        }}

        .story-badge {{
            display: inline-block;
            color: #1a1a2e;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.7em;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .story-category {{
            display: inline-block;
            background: rgba(255,255,255,0.1);
            color: #a8b2d1;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.7em;
            font-weight: 500;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-left: 8px;
            margin-bottom: 8px;
        }}

        .story-title {{
            font-size: 1.15em;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 10px;
            line-height: 1.4;
        }}

        .story-description {{
            font-size: 0.85em;
            color: #a8b2d1;
            line-height: 1.6;
        }}

        .natgeo-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}

        .natgeo-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s ease;
        }}

        .natgeo-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(254, 202, 87, 0.3);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }}

        .natgeo-image {{
            width: 100%;
            height: 120px;
            object-fit: cover;
        }}

        .natgeo-content {{
            padding: 14px;
        }}

        .natgeo-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #feca57, #ff9f43);
            color: #1a1a2e;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.6em;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .natgeo-title {{
            font-size: 0.85em;
            font-weight: 500;
            color: #ffffff;
            text-decoration: none;
            display: block;
            line-height: 1.4;
            transition: color 0.3s ease;
        }}

        .natgeo-title:hover {{
            color: #feca57;
        }}

        /* Responsive Design */
        @media (max-width: 1200px) {{
            .featured-grid {{
                grid-template-columns: 1fr;
            }}

            .natgeo-grid {{
                grid-template-columns: repeat(4, 1fr);
            }}
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 24px 16px;
            }}

            h1 {{
                font-size: 2.2em;
                letter-spacing: 4px;
            }}

            .cards-grid {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}

            .card:not(.card-with-image) {{
                padding: 24px;
            }}

            .card-content {{
                padding: 20px;
            }}

            .card-image-wrapper {{
                height: 200px;
            }}

            .card-meta {{
                flex-wrap: wrap;
                gap: 8px;
            }}

            .domain-header, .featured-header {{
                padding-left: 0;
            }}

            .domain-icon, .featured-icon {{
                width: 48px;
                height: 48px;
                font-size: 1.5em;
            }}

            .domain-title-group h2, .featured-title-group h2 {{
                font-size: 1.3em;
            }}

            .natgeo-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .nasa-media {{
                height: 220px;
            }}

            .stories-grid {{
                grid-template-columns: 1fr;
            }}

            .story-media {{
                height: 180px;
            }}
        }}

        @media (max-width: 480px) {{
            h1 {{
                font-size: 1.8em;
                letter-spacing: 2px;
            }}

            .subtitle {{
                font-size: 0.95em;
            }}

            .card-title {{
                font-size: 1em;
            }}

            .card-bullets li {{
                font-size: 0.85em;
            }}

            .natgeo-grid {{
                grid-template-columns: 1fr;
            }}

            .nasa-title {{
                font-size: 1.1em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SCIENCE DIGEST</h1>
            <p class="subtitle">Your Daily Science News, Made Simple</p>
            <p class="date">{today} &bull; Updated at {update_time}</p>
            <span class="free-badge">100% Free &amp; Open Access Sources</span>
        </header>
"""

    # Add Featured Media Section if we have content
    nasa = featured_media.get("nasa")
    natgeo = featured_media.get("natgeo", [])

    if nasa or natgeo:
        html += """
        <section class="featured-section">
            <div class="featured-header">
                <div class="featured-icon">&#128248;</div>
                <div class="featured-title-group">
                    <h2>Featured Media</h2>
                    <span class="featured-desc">NASA Astronomy Picture of the Day</span>
                </div>
            </div>
            <div class="featured-grid">
"""
        # NASA APOD Card
        if nasa:
            nasa_title = normalize_characters(nasa.get("title", "NASA Image of the Day"))
            nasa_desc = normalize_characters(nasa.get("explanation", ""))

            if nasa.get("media_type") == "video":
                media_html = f'<iframe class="nasa-media-video" src="{nasa["url"]}" allowfullscreen></iframe>'
            else:
                media_html = f'<img class="nasa-media" src="{nasa["url"]}" alt="{nasa_title}" loading="lazy">'

            html += f"""                <div class="nasa-card">
                    {media_html}
                    <div class="nasa-content">
                        <span class="nasa-badge">NASA Picture of the Day</span>
                        <h3 class="nasa-title">{nasa_title}</h3>
                        <p class="nasa-description">{nasa_desc}</p>
                        <p class="nasa-credit">Credit: {nasa.get("copyright", "NASA")}</p>
                    </div>
                </div>
"""

        html += """            </div>
        </section>
"""

    # Generate Wildlife and Climate as two tiles in the same row
    wildlife_articles = domains_articles.get("Wildlife", [])
    climate_articles = domains_articles.get("Climate", [])

    if wildlife_articles or climate_articles:
        html += """
        <section class="featured-section">
            <div class="featured-header">
                <div class="featured-icon" style="background: linear-gradient(135deg, #11998e, #38ef7d);">&#127757;</div>
                <div class="featured-title-group">
                    <h2>Today's Stories</h2>
                    <span class="featured-desc">Wildlife & Climate News</span>
                </div>
            </div>
            <div class="stories-grid">
"""
        # Helper to clean up titles
        def clean_title(title):
            # Fix missing spaces before capitals (e.g., "ZillowThe" -> "Zillow The")
            title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
            # Remove author bylines (By Name, By Name Name)
            title = re.sub(r'By\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*\s*$', '', title).strip()
            # Remove trailing punctuation from cleanup
            title = re.sub(r'[.\s]+$', '', title)
            # Truncate at reasonable length (shorter for card display)
            if len(title) > 70:
                # Try to cut at a word boundary
                title = title[:70].rsplit(' ', 1)[0] + '...'
            return title

        # Wildlife card
        if wildlife_articles:
            article = wildlife_articles[0]
            config = domain_config["Wildlife"]
            title = clean_title(normalize_characters(article['title']))
            explanation = normalize_characters(article.get('explanation', article['summary']))
            image_url = article.get('image')
            # Fallback wildlife image if none found
            if not image_url:
                image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/24701-nature-702702.jpg/1280px-24701-nature-702702.jpg"

            desc_text = explanation.replace('<ul class="summary-bullets">', '').replace('</ul>', '')
            desc_text = re.sub(r'<li>(.*?)</li>', r'\1 ', desc_text).strip()
            if len(desc_text) > 250:
                desc_text = desc_text[:250] + "..."

            html += f"""                <a href="{article['url']}" class="story-card" target="_blank">
"""
            if image_url:
                html += f"""                    <img class="story-media" src="{image_url}" alt="{title}" loading="lazy" onerror="this.style.display='none'">
"""
            html += f"""                    <div class="story-content">
                        <span class="story-badge" style="background: linear-gradient(135deg, {config['color1']}, {config['color2']});">{article['source']}</span>
                        <span class="story-category">Wildlife</span>
                        <h3 class="story-title">{title}</h3>
                        <p class="story-description">{desc_text}</p>
                    </div>
                </a>
"""

        # Climate card
        if climate_articles:
            article = climate_articles[0]
            config = domain_config["Climate"]
            title = clean_title(normalize_characters(article['title']))
            explanation = normalize_characters(article.get('explanation', article['summary']))
            image_url = article.get('image')
            # Fallback climate image if none found
            if not image_url:
                image_url = "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800"

            desc_text = explanation.replace('<ul class="summary-bullets">', '').replace('</ul>', '')
            desc_text = re.sub(r'<li>(.*?)</li>', r'\1 ', desc_text).strip()
            if len(desc_text) > 250:
                desc_text = desc_text[:250] + "..."

            html += f"""                <a href="{article['url']}" class="story-card" target="_blank">
"""
            if image_url:
                html += f"""                    <img class="story-media" src="{image_url}" alt="{title}" loading="lazy" onerror="this.style.display='none'">
"""
            html += f"""                    <div class="story-content">
                        <span class="story-badge" style="background: linear-gradient(135deg, {config['color1']}, {config['color2']});">{article['source']}</span>
                        <span class="story-category">Climate</span>
                        <h3 class="story-title">{title}</h3>
                        <p class="story-description">{desc_text}</p>
                    </div>
                </a>
"""

        html += """            </div>
        </section>
"""

    html += """
        <footer>
            <p>All articles from free, open access sources - no paywalls!</p>
            <p class="sources-list">NASA &bull; Live Science &bull; Inside Climate News</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh Page</button>
        </footer>
    </div>
</body>
</html>
"""

    return html


def select_diverse_articles(articles, count=2):
    """Select articles from different sources to ensure variety."""
    if not articles:
        return []

    if len(articles) <= count:
        return articles

    selected = []
    used_sources = set()

    # First pass: select one article from each unique source
    for article in articles:
        source = article.get('source', 'Unknown')
        if source not in used_sources:
            selected.append(article)
            used_sources.add(source)
            if len(selected) >= count:
                break

    # If we still need more articles (not enough unique sources), fill with remaining
    if len(selected) < count:
        for article in articles:
            if article not in selected:
                selected.append(article)
                if len(selected) >= count:
                    break

    return selected[:count]


def interleave_by_source(articles):
    """Reorder articles to interleave different sources for diversity."""
    if not articles or len(articles) <= 1:
        return articles

    # Group articles by source
    by_source = {}
    for article in articles:
        source = article.get('source', 'Unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(article)

    # Interleave: take one from each source in round-robin fashion
    result = []
    source_lists = list(by_source.values())
    max_len = max(len(lst) for lst in source_lists)

    for i in range(max_len):
        for source_articles in source_lists:
            if i < len(source_articles):
                result.append(source_articles[i])

    return result


def update_digest():
    """Fetch articles and update the HTML page."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating Science Digest...")
    print("  Using only FREE, open access sources (no paywalls)")

    # Fetch featured media (NASA APOD)
    print("  Fetching featured media...")
    print("    Fetching NASA Astronomy Picture of the Day...")
    nasa_data = fetch_nasa_apod()
    if nasa_data:
        print(f"    Got NASA APOD: {nasa_data.get('title', 'Unknown')[:50]}...")
    else:
        print("    NASA APOD not available")

    featured_media = {
        "nasa": nasa_data,
        "natgeo": []  # No longer used, kept for backward compatibility
    }

    domains_articles = {}

    for domain, urls in DOMAIN_URLS.items():
        print(f"  Fetching {domain} articles...")
        articles = fetch_domain_articles(domain, urls)
        print(f"    Found {len(articles)} free articles")

        if articles:
            print(f"    Generating simple explanations...")
            articles = enrich_with_explanations(articles[:3])  # Process a few in case some fail

        # Keep just 1 article for the featured card
        domains_articles[domain] = articles[:1]

    print("  Generating HTML...")
    html = generate_html(domains_articles, featured_media=featured_media)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_FILE)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    total_articles = sum(len(a) for a in domains_articles.values())
    print(f"  Saved {total_articles} articles to: {output_path}")
    print("  Done!")

    return output_path


def run_daemon():
    """Run in daemon mode, updating daily."""
    import schedule

    print("\nRunning in daemon mode - will update daily at 8:00 AM")
    print("Press Ctrl+C to stop\n")

    schedule.every().day.at("08:00").do(update_digest)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def main():
    """Main entry point."""
    print("=" * 60)
    print("  SCIENCE DIGEST - Free & Open Access Science News")
    print("=" * 60)

    # Generate initial digest
    output_path = update_digest()

    # Open in browser (unless --no-browser flag is set)
    if "--no-browser" not in sys.argv:
        print(f"\nOpening in browser...")
        webbrowser.open(f"file://{output_path}")

    # Check for daemon mode
    if "--daemon" in sys.argv or "-d" in sys.argv:
        try:
            run_daemon()
        except ImportError:
            print("\nNote: Install 'schedule' package for daemon mode: pip install schedule")
            print("For now, you can manually run this script daily or set up a cron job.")
    else:
        print("\nTip: Run with --daemon or -d flag for automatic daily updates")
        print(f"\nTo view the digest again, open: {output_path}")


if __name__ == "__main__":
    main()
