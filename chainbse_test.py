import asyncio
from app.services.chainbase_client import ChainbaseClient

async def main():
    async with ChainbaseClient() as client:
        metadata = await client.get_token_metadata(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "ethereum"
        )

        holders = await client.get_token_holders(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "ethereum",
            limit=5
        )
        print(metadata, "\n\n\n", holders)

if __name__ == "__main__":
    asyncio.run(main())
