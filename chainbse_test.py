import asyncio
from app.services.chainbase_client import ChainbaseClient

async def main():
    async with ChainbaseClient() as client:
        metadata = await client.get_token_metadata(
            "So11111111111111111111111111111111111111112",
        )

        holders = await client.get_token_holders(
            "So11111111111111111111111111111111111111112",
            limit=1
        )
        print(metadata, "\n\n\n", holders)

if __name__ == "__main__":
    asyncio.run(main())
