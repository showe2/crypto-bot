import asyncio
from app.services.api.solsniffer_client import SolSnifferClient

async def main():
    async with SolSnifferClient() as client:
        info = await client.get_token_info("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        
        print(info)
if __name__ == "__main__":
    asyncio.run(main())
