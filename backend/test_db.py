import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    
    print("Daily Reports:")
    async for r in db.daily_reports.find():
        print(f"  ID: {r['_id']} - Hours: {r.get('actual_hours')}")
        
    print("\nStudy Logs:")
    async for l in db.study_logs.find():
        print(f"  Topic: {l.get('topic_id')} - Status: {l.get('status_change')}")
        
    print("\nTopics:")
    async for t in db.topics.find({"status": {"$ne": "not_started"}}):
        print(f"  Name: {t.get('name')} - Status: {t.get('status')} - Pct: {t.get('completion_pct')}")

if __name__ == "__main__":
    asyncio.run(main())
