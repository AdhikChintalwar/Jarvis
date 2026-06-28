import subprocess
from urllib.parse import quote_plus
from playwright.async_api import async_playwright


async def search_google(query: str) -> str:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    subprocess.run(["open", url])
    return f"Searched Google for: {query}"


async def search_youtube(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    subprocess.run(["open", url])
    return f"Searched YouTube for: {query}"


async def get_youtube_titles(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        titles = await page.locator("a#video-title").all_text_contents()

        await browser.close()

    cleaned_titles = []

    for title in titles:
        title = title.strip()
        if title and title not in cleaned_titles:
            cleaned_titles.append(title)

    if not cleaned_titles:
        return "I could not find any YouTube video titles."

    top_titles = cleaned_titles[:5]

    result = "Top YouTube results:\n"
    for i, title in enumerate(top_titles, start=1):
        result += f"{i}. {title}\n"

    return result

async def get_youtube_video_details(query: str) -> str:
    from urllib.parse import quote_plus
    from playwright.async_api import async_playwright

    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        videos = page.locator("a#video-title")

        count = await videos.count()

        results = []

        for i in range(min(count, 5)):
            video = videos.nth(i)

            title = await video.get_attribute("title")
            href = await video.get_attribute("href")

            if title and href:
                if href.startswith("/watch") and "v=" in href:
                    video_id = href.split("v=")[1].split("&")[0]
                    full_url = f"https://www.youtube.com/watch?v={video_id}"
                else:
                    continue
                results.append({
                    "title": title.strip(),
                    "url": full_url
                })

        await browser.close()

    if not results:
        return "I could not find video details."

    output = "Top YouTube video details:\n"

    for index, video in enumerate(results, start=1):
        output += f"\n{index}. Title: {video['title']}\n"
        output += f"   URL: {video['url']}\n"

    return output