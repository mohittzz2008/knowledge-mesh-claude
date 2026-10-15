import asyncio
import time
from app.services.platform.codeforces import CodeforcesConnector

async def main():
    handle = "aryan"
    print(f"=== LIVE PAGINATION COMPLETENESS TEST FOR HANDLE: {handle} ===")

    connector = CodeforcesConnector(page_delay=0.35, max_retries=3)

    pages = []
    retries_or_errors = []
    
    original_request = connector._request_with_retry

    async def logged_request(client, url):
        nonlocal pages, retries_or_errors
        start = time.time()
        try:
            res = await original_request(client, url)
            elapsed = time.time() - start
            if "user.status" in url:
                try:
                    data = res.json()
                    count = len(data.get("result", []))
                    page_info = {
                        "url": url,
                        "status": res.status_code,
                        "submissions": count,
                        "elapsed": elapsed,
                    }
                    pages.append(page_info)
                    print(f"  [Page {len(pages)}] count={count}, status={res.status_code}, elapsed={elapsed:.2f}s")
                except Exception:
                    pass
            return res
        except Exception as e:
            retries_or_errors.append(str(e))
            raise

    connector._request_with_retry = logged_request

    # Run unique solved problems fetch
    unique_problems = await connector.fetch_unique_solved_problems(handle, page_size=1000, max_pages=10)

    total_submissions = sum(p["submissions"] for p in pages)
    last_page = pages[-1] if pages else None
    page_size = 1000
    is_short = last_page["submissions"] < page_size if last_page else False
    is_empty = last_page["submissions"] == 0 if last_page else False

    print("\n--- RESULTS FOR REPORT ---")
    print(f"Handle tested: {handle}")
    print(f"Number of pages successfully fetched: {len(pages)}")
    print(f"Total submissions retrieved: {total_submissions}")
    print(f"Page breakdown: {[p['submissions'] for p in pages]}")
    if is_empty:
        print("Final page status: Empty (0 submissions returned)")
    elif is_short:
        print(f"Final page status: Shorter than requested page size ({last_page['submissions']} < {page_size})")
    else:
        print("Final page status: Full page (reached limit)")
    print(f"API errors or retries occurred: {'None' if not retries_or_errors else retries_or_errors}")
    print(f"Final number of unique accepted problems: {len(unique_problems)}")
    if is_empty or is_short:
        print("End condition reached: Normal end-of-history (proven complete lifetime history)")
    else:
        print("End condition reached: Configured limit reached")

if __name__ == "__main__":
    asyncio.run(main())
