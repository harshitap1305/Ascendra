import asyncio
from app.database import init_db, close_db
from app.models.daily_report import DailyReport
from app.models.study_log import StudyLog
from app.models.topic import Topic
from app.models.feedback import Feedback

async def main():
    await init_db()
    
    print("Daily Reports:")
    reports = await DailyReport.find_all().to_list()
    for r in reports:
        print(f"  ID: {r.id} - Hours: {r.actual_hours}")
        
    print("\nStudy Logs:")
    logs = await StudyLog.find_all().to_list()
    for l in logs:
        print(f"  Topic: {l.topic_id} - Status: {l.status_change}")
        
    print("\nFeedback:")
    feedbacks = await Feedback.find_all().to_list()
    for f in feedbacks:
        print(f"  ID: {f.id}")

    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
