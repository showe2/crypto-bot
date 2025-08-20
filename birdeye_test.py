import asyncio
from app.services.birdeye_client import BirdeyeClient

async def main():
    async with BirdeyeClient() as client:
        price = await client.get_token_price(
            "So11111111111111111111111111111111111111112",
        )

        # UNAVAILABLE - REQUIRES PLAN UPGRADE
        # metadata = await client.get_token_metadata(
        #     "So11111111111111111111111111111111111111112",
        # )

        trades = await client.get_token_trades(
            "So11111111111111111111111111111111111111112",
            limit=10
        )

        trending = await client.get_trending_tokens(
            limit=5
        )

        # UNAVAILABLE - REQUIRES PLAN UPGRADE
        # query = {"keyword":"Sol","chain":"all","target":"all","search_mode":"exact","offset":"0,"ui_amount_mode":"scaled"}
        # trades = await client.search_tokens(
        #     query,
        #     limit=10
        # )

        price_history = await client.get_price_history(
            token_address="So11111111111111111111111111111111111111112",
            time_from=0,
            time_to=1726704000
        )

        top_traders = await client.get_top_traders(
            token_address="So11111111111111111111111111111111111111112",
            limit=3
        )

        print(top_traders)

if __name__ == "__main__":
    asyncio.run(main())
