import asyncio
from app.services.dexscreener_client import DexScreenerClient

async def main():
    async with DexScreenerClient() as client:
        pairs = await client.get_pair_by_address("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

        print(pairs)

if __name__ == "__main__":
    asyncio.run(main())
