import asyncio
from app.services.dexscreener_client import DexScreenerClient

async def main():
    async with DexScreenerClient() as client:
        pairs = await client.get_tokens_by_addresses(["So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"])

        print(pairs)

if __name__ == "__main__":
    asyncio.run(main())
