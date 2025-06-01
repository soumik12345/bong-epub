import tempfile
from io import BytesIO
from typing import Optional, Union

import pypub
import requests
from bs4 import BeautifulSoup
from PIL import Image
from rich.progress import track


def extract_preview_links_and_titles(page_url: str) -> dict[str, str]:
    response = requests.get(page_url)
    response.raise_for_status()
    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")
    result_mapping: dict[str, str] = {}
    preview_divs = soup.find_all("div", class_="ld-item-list-item-preview")

    for preview_div in preview_divs:
        anchor_tag = preview_div.find("a", href=True)
        if anchor_tag is None:
            continue
        link_url = anchor_tag["href"].strip()

        title_div = anchor_tag.find("div", class_="ld-item-title")
        if title_div is None:
            continue

        title_text = title_div.get_text(strip=True)
        result_mapping[title_text] = link_url

    return result_mapping


def get_paragraphs_from_url(url: str, timeout: float = 10.0) -> list[str]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        raise

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type:
        raise ValueError(
            f"URL did not return HTML content (Content-Type: {content_type!r})"
        )

    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = soup.find_all("p")
    paragraphs = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)][
        :-12
    ]
    return "\n\n".join(paragraphs)


def get_title_and_author(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        raise RuntimeError(f"Failed to fetch URL {url}")

    soup = BeautifulSoup(response.text, "html.parser")
    header_tags = soup.find_all(class_="page-header-title")
    titles = [tag.get_text(strip=True) for tag in header_tags][0]
    return titles.split(" – ")


def get_cover_picture(
    url: str, timeout: float = 10.0
) -> Optional[Union[str, Image.Image]]:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()  # Will raise if status != 200

    soup = BeautifulSoup(response.text, "html.parser")

    picture_tag = soup.find("picture")
    if not picture_tag:
        return None

    source_tag = picture_tag.find("source")
    if not source_tag:
        return None

    image_url = source_tag.get("srcset").split(" ")[0]

    try:
        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()
        return Image.open(BytesIO(img_response.content))
    except requests.RequestException:
        return None


def save_book(
    book: dict[str, str],
    save_file: str,
    title: str,
    author: str,
    cover_image: Optional[Image.Image] = None,
):
    epub_file = pypub.Epub(title, creator=author, language="bn")
    temp_file = None

    if cover_image:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        cover_image.save(temp_file.name)
        epub_file.cover = temp_file.name

    for chapter_title, chapter_content in track(
        book.items(), total=len(book), description="Adding chapters to EPUB"
    ):
        epub_file.add_chapter(
            pypub.create_chapter_from_text(chapter_content, chapter_title)
        )
    epub_file.create(save_file)

    if temp_file:
        temp_file.close()


def scrape_book_from_url(url: str, save_file: Optional[str] = None) -> dict[str, str]:
    chapter_links = extract_preview_links_and_titles(url)
    title, author = get_title_and_author(url)
    cover_picture = get_cover_picture(url)
    book = {}
    for chapter_title, chapter_url in track(
        chapter_links.items(),
        total=len(chapter_links),
        description="Scraping chapters",
    ):
        chapter_content = get_paragraphs_from_url(chapter_url)
        book[chapter_title] = chapter_content

    if save_file:
        save_file = f"{title}-{author}.epub"

    save_book(book, save_file, title, author, cover_picture)

    return {
        "title": title,
        "author": author,
        "cover_picture": cover_picture,
        "book": book,
    }
