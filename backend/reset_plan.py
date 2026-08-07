import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from bson import ObjectId

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    
    plan_id = ObjectId("6a757ae5216eb7e211bccf4e")
    
    # Set daily_plan status back to pending
    res = await db.daily_plans.update_one({"_id": plan_id}, {"$set": {"status": "pending"}})
    print(f"Updated daily_plan: {res.modified_count}")
    
    # Delete daily_report for this plan
    report = await db.daily_reports.find_one({"daily_plan_id": plan_id})
    if report:
        report_id = report["_id"]
        res2 = await db.daily_reports.delete_one({"_id": report_id})
        print(f"Deleted daily_report: {res2.deleted_count}")
        
        # Delete feedback
        res3 = await db.feedback.delete_many({"daily_report_id": report_id})
        print(f"Deleted feedback: {res3.deleted_count}")
        
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
