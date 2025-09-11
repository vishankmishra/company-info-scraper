import os
import scrapy

class FullPageSpider(scrapy.Spider):
    name = "fullpage"
    start_urls = ['https://www.tasconnect.com/']  # replace with your URL

    def parse(self, response):
        # Save the HTML of the page
        page_name = response.url.split("/")[-1] or "index"
        file_path = f"www.tasconnect.com/{page_name}.html"

        os.makedirs("www.tasconnect.com/", exist_ok=True)  # create folder if it doesn't exist
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        self.logger.info(f"Saved file {file_path}")

        # Follow all valid links on the page
        for href in response.css("a::attr(href)").getall():
            if not href or href.startswith(("javascript:", "#")):
                continue
            yield response.follow(href, self.parse)