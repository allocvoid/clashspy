import aiohttp
import asyncio
import urllib.parse
from typing import Optional


class ClashRoyaleAPI:
    BASE_URL = "https://api.clashroyale.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _encode_tag(self, tag: str) -> str:
        """Encode player/clan tag for URL (# -> %23)"""
        if not tag.startswith("#"):
            tag = "#" + tag
        return urllib.parse.quote(tag)

    async def _request(self, endpoint: str, retries: int = 3) -> dict:
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        last_error = None
        for attempt in range(retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        raise ValueError("Player or resource not found")
                    elif response.status == 403:
                        raise PermissionError("API key invalid or IP not whitelisted")
                    elif response.status == 429:
                        # Rate limited, wait and retry
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        error_data = await response.json()
                        raise Exception(f"API Error {response.status}: {error_data.get('message', 'Unknown error')}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise

        if last_error:
            raise last_error

    async def get_player(self, tag: str) -> dict:
        """Get player information"""
        encoded_tag = self._encode_tag(tag)
        return await self._request(f"/players/{encoded_tag}")

    async def get_player_battles(self, tag: str) -> list:
        """Get player's battle log"""
        encoded_tag = self._encode_tag(tag)
        return await self._request(f"/players/{encoded_tag}/battlelog")

    async def get_player_chests(self, tag: str) -> dict:
        """Get player's upcoming chests"""
        encoded_tag = self._encode_tag(tag)
        return await self._request(f"/players/{encoded_tag}/upcomingchests")

    async def get_clan(self, tag: str) -> dict:
        """Get clan information"""
        encoded_tag = self._encode_tag(tag)
        return await self._request(f"/clans/{encoded_tag}")

    async def get_all_cards(self) -> dict:
        """Get all available cards"""
        return await self._request("/cards")
