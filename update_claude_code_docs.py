#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#   "requests",
# ]
# ///

import re
import sys
import requests
from pathlib import Path

def main():
    # Get target directory from command line or use current directory
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    docs_dir = target_dir / "claude-code-docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Download the docs map
    print("Downloading docs map...")
    response = requests.get("https://docs.anthropic.com/en/docs/claude-code/claude_code_docs_map.md")
    response.raise_for_status()
    
    # Find all claude-code URLs
    pattern = r'https://docs\.anthropic\.com/en/docs/claude-code/([a-z-]+)'
    matches = re.findall(pattern, response.text)
    
    # Remove duplicates while preserving order
    pages = list(dict.fromkeys(matches))
    
    print(f"Found {len(pages)} documentation pages")
    
    # Download each page
    for page in pages:
        print(f"Downloading {page}...")
        try:
            url = f"https://docs.anthropic.com/en/docs/claude-code/{page}.md"
            page_response = requests.get(url)
            page_response.raise_for_status()
            
            # Save to file (overwrites if exists)
            file_path = docs_dir / f"{page}.md"
            file_path.write_text(page_response.text)
            print(f"  ✓ Saved {page}.md")
        except Exception as e:
            print(f"  ✗ Failed to download {page}: {e}")
    
    print(f"\nDone! Documentation saved to {docs_dir}")

if __name__ == "__main__":
    main()