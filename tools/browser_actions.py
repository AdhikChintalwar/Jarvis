from playwright.async_api import async_playwright
from urllib.parse import quote_plus


async def search_google(query: str) -> str:
    url = f"https://www.google.com/search?q={quote_plus(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300
        )

        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        return f"Searched Google for: {query}"


async def search_youtube(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300
        )

        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        return f"Searched YouTube for: {query}"