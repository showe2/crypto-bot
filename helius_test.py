import asyncio
from app.services.helius_client import HeliusClient

async def main():
    async with HeliusClient() as client:
        holders = await client.get_token_accounts("he1iusmfkpAdwvxLNGV8Y1iSbj4rUy6yMhEA3fotn9A")

        supply = await client.get_token_supply("he1iusmfkpAdwvxLNGV8Y1iSbj4rUy6yMhEA3fotn9A")

        meta = await client.get_token_metadata(["he1iusmfkpAdwvxLNGV8Y1iSbj4rUy6yMhEA3fotn9A"])

        print(holders, "\n\n\n", supply, "\n\n\n", meta)

if __name__ == "__main__":
    asyncio.run(main())
