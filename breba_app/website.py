from datetime import timezone, datetime
from html.parser import HTMLParser

from breba_app.paths import templates


class CanonicalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical_url = None

    def handle_starttag(self, tag, attrs):
        # Look for <link> tags
        if tag == 'link':
            attrs_dict = dict(attrs)
            # Check if it's a canonical link
            if attrs_dict.get('rel') == 'canonical':
                self.canonical_url = attrs_dict.get('href')


def get_canonical_url(html: str) -> str:
    parser = CanonicalParser()
    parser.feed(html)
    return parser.canonical_url


def generate_sitemap_xml(urls: list[dict]):
    time_now = datetime.now(timezone.utc).date().isoformat()
    sitemap_template = templates.get_template("sitemap.xml")
    return sitemap_template.render(urls=urls, now=time_now)


def generate_robots_txt(canonical_url: str):
    canonical_url = canonical_url.rstrip("/")
    return f"""User-agent: *
Allow: /

Sitemap: {canonical_url}/sitemap.xml"""


if __name__ == "__main__":
    urls_list = [
        {
            'loc': 'https://example.com/'
        },
        {
            'loc': 'https://example.com/about'
        },
        {
            'loc': 'https://example.com/contact'
        }
    ]
    print(generate_sitemap_xml(urls_list))
    print(generate_robots_txt("https://example.com/"))
