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
        ],
    )


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
