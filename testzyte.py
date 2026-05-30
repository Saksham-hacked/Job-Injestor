import requests
from bs4 import BeautifulSoup

response = requests.post(
    "https://api.zyte.com/v1/extract",
    auth=("2181dfe7e4034a949ec87688f9b6c9b2", ""),
    json={
        "url": "https://www.searchpeoplefree.com/find/john-doe/ca/los-angeles",
        "browserHtml": True,  # <-- this handles JS rendering automatically
    },
)

print("Status:", response.status_code)

if response.status_code == 200:
    html = response.json()["browserHtml"]
    soup = BeautifulSoup(html, "html.parser")
    print(soup.prettify()[:3000])
else:
    print("Error:", response.text)