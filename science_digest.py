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
    "nationalgeographic.com",  # Often has subscription walls
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
    "Biology": [
        "animal", "species", "cell", "dna", "gene", "evolution", "fossil",
        "dinosaur", "bacteria", "virus", "protein", "organism", "ecosystem",
        "wildlife", "plant", "insect", "mammal", "bird", "fish", "marine",
        "ocean life", "biodiversity", "extinction", "endangered", "habitat",
        "genetics", "mutation", "enzyme", "microbe", "biology", "life form",
        "creature", "predator", "prey", "reproduction", "anatomy", "brain",
        "neuron", "disease", "infection", "immune", "coral", "reef", "forest"
    ],
    "Climate": [
        "climate", "weather", "temperature", "warming", "carbon", "emission",
        "greenhouse", "ice", "glacier", "arctic", "antarctic", "sea level",
        "drought", "flood", "hurricane", "storm", "atmosphere", "pollution",
        "renewable", "energy", "fossil fuel", "ocean warming", "heat wave",
        "wildfire", "deforestation", "methane", "ozone", "el nino", "la nina",
        "precipitation", "rainfall", "snowfall", "permafrost", "ecosystem change",
        "environmental", "sustainability", "conservation", "earth", "global"
    ]
}

# FREE, open access URLs organized by domain
# These sources provide full articles without paywalls
DOMAIN_URLS = {
    "Astronomy": [
        # ScienceDaily - completely free
        "https://www.sciencedaily.com/news/space_time/",
        "https://www.sciencedaily.com/news/space_time/astronomy/",
        # Phys.org - free science news
        "https://phys.org/space-news/",
        "https://phys.org/space-news/astronomy/",
        # EurekAlert - free press releases from research institutions
        "https://www.eurekalert.org/news-releases/browse/subject/space",
        # Space.com - mostly free
        "https://www.space.com/science",
        # NASA - government, always free
        "https://www.nasa.gov/news/all-news/",
    ],
    "Biology": [
        # ScienceDaily - completely free
        "https://www.sciencedaily.com/news/plants_animals/",
        "https://www.sciencedaily.com/news/plants_animals/biology/",
        # Phys.org - free science news
        "https://phys.org/biology-news/",
        "https://phys.org/biology-news/ecology/",
        # EurekAlert - free press releases
        "https://www.eurekalert.org/news-releases/browse/subject/biology",
        # Live Science - mostly free
        "https://www.livescience.com/animals",
    ],
    "Climate": [
        # ScienceDaily - completely free
        "https://www.sciencedaily.com/news/earth_climate/",
        "https://www.sciencedaily.com/news/earth_climate/climate/",
        # Phys.org - free science news
        "https://phys.org/earth-news/",
        "https://phys.org/earth-news/climate-change/",
        # EurekAlert - free press releases
        "https://www.eurekalert.org/news-releases/browse/subject/environment",
        # NOAA - government, always free
        "https://www.noaa.gov/news-release",
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
        return None


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


def simplify_text(text):
    """Simplify text to approximately 7th grade reading level."""
    # First normalize special characters
    text = normalize_characters(text)

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

    # Build HTML bullet list
    html_parts = ['<ul class="summary-bullets">']
    for point in bullet_points[:3]:
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
    return ""


def get_source_name(url):
    """Get display name for a source URL."""
    if "sciencedaily" in url:
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

    for url in urls:
        if len(articles) >= 6:  # Fetch extra to have options after filtering
            break

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find article elements based on source
            if "sciencedaily" in url:
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
                if len(articles) >= 6:
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
                    detected_domain = classify_domain(headline, summary)
                    if detected_domain != domain:
                        continue

                    seen_titles.add(headline)

                    articles.append({
                        "title": headline,
                        "summary": summary[:400] if len(summary) > 400 else summary,
                        "url": href or url,
                        "source": get_source_name(url),
                        "domain": domain
                    })

                except Exception:
                    continue

        except Exception as e:
            print(f"    Warning: Could not fetch {url}: {e}", file=sys.stderr)
            continue

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
        "Astronomy": {"icon": "&#127776;", "class": "astronomy", "desc": "Stars, Planets & Space"},
        "Biology": {"icon": "&#129516;", "class": "biology", "desc": "Life & Living Things"},
        "Climate": {"icon": "&#127758;", "class": "climate", "desc": "Weather & Environment"},
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
            grid-template-columns: repeat(4, 1fr);
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
            grid-template-columns: 1.5fr 1fr;
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
        @media (max-width: 1400px) {{
            .cards-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

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
                    <span class="featured-desc">NASA Picture of the Day & Nature Photography</span>
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

        # NatGeo Cards Grid
        if natgeo:
            html += """                <div class="natgeo-grid">
"""
            for item in natgeo[:4]:
                item_title = normalize_characters(item.get("title", ""))
                item_source = item.get("source", "Nature News")
                # Only show items with images
                if item.get("image"):
                    html += f"""                    <a href="{item.get('url', '#')}" class="natgeo-card" target="_blank">
                        <img class="natgeo-image" src="{item.get('image', '')}" alt="{item_title}" loading="lazy">
                        <div class="natgeo-content">
                            <span class="natgeo-badge">{item_source}</span>
                            <span class="natgeo-title">{item_title}</span>
                        </div>
                    </a>
"""
            html += """                </div>
"""

        html += """            </div>
        </section>
"""

    for domain in ["Astronomy", "Biology", "Climate"]:
        articles = domains_articles.get(domain, [])
        config = domain_config[domain]

        html += f"""
        <section class="domain-section">
            <div class="domain-header">
                <div class="domain-icon {config['class']}-icon">{config['icon']}</div>
                <div class="domain-title-group">
                    <h2>{domain}</h2>
                    <span class="domain-desc">{config['desc']}</span>
                </div>
            </div>
            <div class="cards-grid">
"""
        if articles:
            for article in articles[:4]:
                # Normalize all text to fix encoding issues
                title = normalize_characters(article['title'])
                explanation = normalize_characters(article.get('explanation', article['summary']))
                read_time = article.get('read_time', 2)
                image_url = article.get('image')

                # Extract bullet points from explanation HTML
                bullets_html = explanation

                # Build card HTML with optional image - entire card is clickable
                card_html = f"""                <a href="{article['url']}" class="card{'  card-with-image' if image_url else ''}" target="_blank">
"""
                # Add image if available
                if image_url:
                    card_html += f"""                    <div class="card-image-wrapper">
                        <img class="card-image" src="{image_url}" alt="{title}" loading="lazy" onerror="this.parentElement.style.display='none'">
                    </div>
"""
                card_html += f"""                    <div class="card-content">
                        <div class="card-meta">
                            <span class="card-source">{article['source']}</span>
                            <span class="card-read-time">{read_time} min read</span>
                        </div>
                        <h3 class="card-title">{title}</h3>
                        <ul class="card-bullets">
                            {bullets_html.replace('<ul class="summary-bullets">', '').replace('</ul>', '').replace('<li>', '<li>').replace('</li>', '</li>')}
                        </ul>
                    </div>
                </a>
"""
                html += card_html
        else:
            html += """                <div class="no-articles">No articles available in this category today. Check back tomorrow!</div>
"""

        html += """            </div>
        </section>
"""

    html += """
        <footer>
            <p>All articles from free, open access sources - no paywalls!</p>
            <p class="sources-list">ScienceDaily &bull; Phys.org &bull; EurekAlert &bull; NASA &bull; NOAA &bull; Space.com &bull; Live Science</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh Page</button>
        </footer>
    </div>
</body>
</html>
"""

    return html


def update_digest():
    """Fetch articles and update the HTML page."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating Science Digest...")
    print("  Using only FREE, open access sources (no paywalls)")

    # Fetch featured media (NASA APOD and NatGeo RSS)
    print("  Fetching featured media...")
    print("    Fetching NASA Astronomy Picture of the Day...")
    nasa_data = fetch_nasa_apod()
    if nasa_data:
        print(f"    Got NASA APOD: {nasa_data.get('title', 'Unknown')[:50]}...")
    else:
        print("    NASA APOD not available")

    print("    Fetching nature/science RSS feeds...")
    nature_items = fetch_nature_feeds()
    print(f"    Found {len(nature_items)} nature items with images")

    featured_media = {
        "nasa": nasa_data,
        "natgeo": nature_items  # Key kept as "natgeo" for backward compatibility with HTML
    }

    domains_articles = {}

    for domain, urls in DOMAIN_URLS.items():
        print(f"  Fetching {domain} articles...")
        articles = fetch_domain_articles(domain, urls)
        print(f"    Found {len(articles)} free articles")

        if articles:
            print(f"    Generating simple explanations...")
            articles = enrich_with_explanations(articles[:5])  # Process a few extra in case some fail

        domains_articles[domain] = articles[:4]  # Keep top 4

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
