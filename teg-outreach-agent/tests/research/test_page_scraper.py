import httpx
import respx

from app.research.tools import ResearchQuery
from app.research.page_scraper import PageScraper

HTML = """<html><body><article>
<h1>Acme Corp</h1>
<p>Acme Corp is a 40-person software company in Ahmedabad building ERP tools.</p>
</article></body></html>"""


@respx.mock
async def test_scrape_extracts_text():
    respx.get("https://acme.example/about").mock(
        return_value=httpx.Response(200, html=HTML)
    )
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="https://acme.example/about", context="", want=["page_text"],
    ))
    assert r.available is True
    assert "Ahmedabad" in r.fields["page_text"]
    assert r.source_url == "https://acme.example/about"


@respx.mock
async def test_scrape_http_error_unavailable():
    respx.get("https://acme.example/404").mock(return_value=httpx.Response(404))
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="https://acme.example/404", context="", want=["page_text"],
    ))
    assert r.available is False


async def test_scrape_non_url_unavailable():
    r = await PageScraper().lookup(ResearchQuery(
        track="company", subject="Acme Corp", context="", want=["page_text"],
    ))
    assert r.available is False
