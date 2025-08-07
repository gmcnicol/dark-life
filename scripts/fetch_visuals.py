import os
import re
import requests
import frontmatter
from pathlib import Path

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

if not PEXELS_API_KEY:
    raise RuntimeError("PEXELS_API_KEY environment variable is required")

HEADERS = {"Authorization": PEXELS_API_KEY}

# Timeout for all network requests (seconds)
REQUEST_TIMEOUT = 10

def extract_keywords_from_story(filepath):
    """Extract nouns or key phrases from the story text (simple heuristic)."""
    post = frontmatter.load(filepath)
    text = post.content.lower()
    matches = re.findall(r"\b(?:cabin|window|scream|fog|shadow|basement|attic|forest|creak|blood|scream|hallway|noise|silhouette|scratching|isolation|abandoned|night|mist|dark|alley|bathroom|whisper|fear|ritual|doll|figure|eyes|sleep)\b", text)
    return list(set(matches))

def fetch_images(keywords, out_dir, per_keyword=3):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for keyword in keywords:
        params = {
            "query": keyword,
            "per_page": per_keyword
        }
        try:
            response = requests.get(
                PEXELS_SEARCH_URL,
                headers=HEADERS,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed for {keyword}: {e}")
            continue
        data = response.json()
        for i, photo in enumerate(data.get("photos", [])):
            url = photo["src"]["original"]
            ext = Path(url).suffix
            out_path = Path(out_dir) / f"{keyword}_{i}{ext}"
            try:
                with requests.get(
                    url, timeout=REQUEST_TIMEOUT, stream=True
                ) as img_resp:
                    img_resp.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in img_resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                print(f"Downloaded: {out_path}")
            except requests.RequestException as e:
                print(f"Failed to download {url}: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--story", required=True, help="Path to Markdown story file")
    parser.add_argument("--out", default="content/visuals", help="Directory to save images")

    args = parser.parse_args()

    keywords = extract_keywords_from_story(args.story)
    print(f"Extracted keywords: {keywords}")
    fetch_images(keywords, args.out)
