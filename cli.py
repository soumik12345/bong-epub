import fire

from bong_kindle.scrape import scrape_book_from_url


def main():
    fire.Fire(scrape_book_from_url)


if __name__ == "__main__":
    main()
