import asyncio
from app.services.api.solanafm_client import SolanaFMClient

async def main():
    async with SolanaFMClient() as client:
        account_info = await client.get_account_detail("AK2VbkdYLHSiJKS6AGUfNZYNaejABkV6VYDX1Vrgxfo")

        token_info = await client.get_token_info("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

        print(token_info)

if __name__ == "__main__":
    asyncio.run(main())
