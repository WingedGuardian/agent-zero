import aiohttp
from python.helpers import runtime

URL = "http://localhost:55510/search"
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB


async def search(query:str):
    return await runtime.call_development_function(_search, query=query)

async def _search(query:str):
    import json
    async with aiohttp.ClientSession() as session:
        async with session.post(URL, data={"q": query, "format": "json"}) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                raise ValueError(
                    f"Search response too large: {content_length} bytes (limit: {MAX_RESPONSE_SIZE})"
                )
            body = await response.read()
            if len(body) > MAX_RESPONSE_SIZE:
                raise ValueError(
                    f"Search response too large: {len(body)} bytes (limit: {MAX_RESPONSE_SIZE})"
                )
            return json.loads(body)
