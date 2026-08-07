import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    
    print("Daily Plans:")
    async for r in db.daily_plans.find():
        print(f"  ID: {r['_id']} - Tasks: {r.get('tasks')}")

if __name__ == "__main__":
    asyncio.run(main())
