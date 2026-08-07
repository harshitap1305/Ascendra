import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    print(f"Dropping database: {settings.DATABASE_NAME}")
    await client.drop_database(settings.DATABASE_NAME)
    print("Database cleared successfully! You have a fresh slate.")

if __name__ == "__main__":
    asyncio.run(main())
