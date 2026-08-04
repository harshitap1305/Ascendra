from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.config import settings


# Import all document models here so Beanie knows about them at init time
from app.models.user import User
from app.models.exam import Exam
from app.models.topic import Topic
from app.models.raw_syllabus import RawSyllabusUpload
from app.models.resource import Resource
from app.models.ai_interaction import AIInteraction
from app.models.module_start import ModuleStart
from app.models.module_plan import ModulePlan
from app.models.module_plan_day import ModulePlanDay
from app.models.module_resource import ModuleResource
from app.models.daily_plan import DailyPlan
from app.models.daily_report import DailyReport
from app.models.study_log import StudyLog
from app.models.feedback import Feedback
from app.models.weekly_review import WeeklyReview
from app.models.monthly_review import MonthlyReview
from app.models.revision_schedule import RevisionSchedule
from app.models.confidence_log import ConfidenceLog

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    await init_beanie(
        database=_client[settings.DATABASE_NAME],
        document_models=[
            User,
            Exam,
            Topic,
            RawSyllabusUpload,
            Resource,
            AIInteraction,
            ModuleStart,
            ModulePlan,
            ModulePlanDay,
            ModuleResource,
            DailyPlan,
            DailyReport,
            StudyLog,
            Feedback,
            WeeklyReview,
            MonthlyReview,
            RevisionSchedule,
            ConfidenceLog,
        ],
    )


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
