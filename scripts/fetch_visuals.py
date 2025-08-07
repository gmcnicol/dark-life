import os
import re
import requests
import frontmatter
from pathlib import Path

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

HEADERS = {
    "Authorization": PEXELS_API_KEY
}

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
        response = requests.get(PEXELS_SEARCH_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Failed for {keyword}: {response.status_code}")
            continue
        data = response.json()
        for i, photo in enumerate(data.get("photos", [])):
            url = photo["src"]["original"]
            ext = Path(url).suffix
            out_path = Path(out_dir) / f"{keyword}_{i}{ext}"
            with open(out_path, "wb") as f:
                f.write(requests.get(url).content)
            print(f"Downloaded: {out_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--story", required=True, help="Path to Markdown story file")
    parser.add_argument("--out", default="content/visuals", help="Directory to save images")

    args = parser.parse_args()

    if not PEXELS_API_KEY:
        raise RuntimeError("Set PEXELS_API_KEY in environment")

    keywords = extract_keywords_from_story(args.story)
    print(f"Extracted keywords: {keywords}")
    fetch_images(keywords, args.out)