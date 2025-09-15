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
from urllib.parse import urlparse
import time

def extract_urls_from_llms_txt(content: str) -> list[str]:
    """Extract all Pydantic AI documentation URLs from llms.txt content."""
    # Pattern to match URLs in the format (https://ai.pydantic.dev/path/to/file.md)
    pattern = r'\(https://ai\.pydantic\.dev/[^)]+\.md\)'
    matches = re.findall(pattern, content)

    # Remove the parentheses from each match
    urls = [match.strip('()') for match in matches]

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls

def url_to_filepath(url: str) -> Path:
    """Convert a documentation URL to a local file path."""
    # Parse the URL to get the path component
    parsed = urlparse(url)
    path = parsed.path

    # Remove leading slash and .md extension
    if path.startswith('/'):
        path = path[1:]
    if path.endswith('.md'):
        path = path[:-3]

    # Replace slashes with underscores for flat directory structure
    # This makes it easier to search and avoids deep nesting
    filename = path.replace('/', '_') + '.md'

    return Path(filename)

def main():
    # Get target directory from command line or use current directory
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    docs_dir = target_dir / "pydantic-ai-docs"
    docs_dir.mkdir(exist_ok=True)

    # Download the llms.txt mapper file
    print("Downloading Pydantic AI documentation mapper...")
    try:
        response = requests.get("https://ai.pydantic.dev/llms.txt", timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to download mapper file: {e}")
        sys.exit(1)

    # Extract all documentation URLs
    urls = extract_urls_from_llms_txt(response.text)
    print(f"Found {len(urls)} documentation pages")

    # Track statistics
    successful = 0
    failed = 0

    # Download each documentation page
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Downloading {url}...")

        try:
            # Add a small delay to be respectful to the server
            if i > 1:
                time.sleep(0.05)

            # Download the page
            page_response = requests.get(url, timeout=30)
            page_response.raise_for_status()

            # Determine the local file path
            file_path = docs_dir / url_to_filepath(url)

            # Save the content
            file_path.write_text(page_response.text, encoding='utf-8')

            # Also create a mapping file for reference
            mapping_file = docs_dir / "_url_mapping.txt"
            with open(mapping_file, 'a', encoding='utf-8') as f:
                f.write(f"{file_path.name} -> {url}\n")

            print(f"  ✓ Saved as {file_path.name}")
            successful += 1

        except requests.HTTPError as e:
            print(f"  ✗ HTTP error {e.response.status_code}: {e}")
            failed += 1
        except requests.RequestException as e:
            print(f"  ✗ Request failed: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            failed += 1

    # Create a summary file with metadata
    summary_file = docs_dir / "_summary.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"# Pydantic AI Documentation Summary\n\n")
        f.write(f"Downloaded on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total pages: {len(urls)}\n")
        f.write(f"Successfully downloaded: {successful}\n")
        f.write(f"Failed: {failed}\n\n")
        f.write(f"Source: https://ai.pydantic.dev/llms.txt\n")

    # Final summary
    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"  Successfully downloaded: {successful} pages")
    if failed > 0:
        print(f"  Failed: {failed} pages")
    print(f"  Documentation saved to: {docs_dir}")
    print(f"  URL mapping saved to: {docs_dir / '_url_mapping.txt'}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()