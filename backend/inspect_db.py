import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client.get_database()
    
    print("Daily Reports:")
    async for r in db.dailyreport.find():
        print(f"  {r['_id']} - Hours: {r.get('actual_hours')}")
        
    print("\nStudy Logs:")
    async for l in db.studylog.find():
        print(f"  {l['_id']} - Topic: {l.get('topic_id')} - Status: {l.get('status_change')}")
        
    print("\nTopics:")
    async for t in db.topic.find({"status": {"$ne": "not_started"}}):
        print(f"  {t['_id']} - Name: {t.get('name')} - Status: {t.get('status')} - Pct: {t.get('completion_pct')}")

    print("\nFeedback:")
    async for f in db.feedback.find():
        print(f"  {f['_id']} - Adjustments: {f.get('adjustment_summary')}")

if __name__ == "__main__":
    asyncio.run(main())
