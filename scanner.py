import httpx
from bs4 import BeautifulSoup

CITY = "dallas"
CATEGORY = "fua"
ZIP_CODE = "75036"
RADIUS_MILES = 50
SEARCH_QUERY = "office chair"

url = (
    f"https://{CITY}.craigslist.org/search/{CATEGORY}"
    f"?postal={ZIP_CODE}&search_distance={RADIUS_MILES}&query={SEARCH_QUERY.replace(' ', '+')}"
)

response = httpx.get(url)
soup = BeautifulSoup(response.text, "html.parser")

listings = []
for listing in soup.select(".cl-static-search-result"):
    title = listing.select_one(".title")
    price = listing.select_one(".price")
    link = listing.select_one("a")

    if title and link:
        listings.append({
            "title": title.text.strip(),
            "price": price.text.strip() if price else "No price",
            "url": link["href"]
        })

# Now visit each listing page and grab images
for listing in listings[:3]:  # limit to 3 for now while testing
    detail = httpx.get(listing["url"])
    detail_soup = BeautifulSoup(detail.text, "html.parser")

    images = detail_soup.select(".swipe-wrap img")
    image_urls = [img["src"] for img in images if img.get("src")]

    listing["images"] = image_urls
    print(f"\n{listing['title']} — {listing['price']}")
    print(f"Images: {image_urls}")