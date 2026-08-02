from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from beanie import PydanticObjectId

from app.models.exam import Exam
from app.models.topic import Topic
from app.models.user import User
from app.schemas.exam import ExamCreate, ExamUpdate, ExamResponse, ExamSummaryResponse
from app.api.deps import get_current_user, get_exam_for_user
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/exams", tags=["exams"])


def _exam_to_response(exam: Exam) -> ExamResponse:
    return ExamResponse(
        id=str(exam.id),
        user_id=str(exam.user_id),
        name=exam.name,
        description=exam.description,
        exam_date=exam.exam_date,
        target_finish_date=exam.target_finish_date,
        daily_study_hours=exam.daily_study_hours,
        experience_level=exam.experience_level,
        goal_score=exam.goal_score,
        status=exam.status,
        created_at=exam.created_at,
    )


@router.post("", response_model=ExamResponse, status_code=201)
async def create_exam(
    body: ExamCreate,
    current_user: User = Depends(get_current_user),
):
    exam = Exam(user_id=current_user.id, **body.model_dump())
    await exam.insert()
    return _exam_to_response(exam)


@router.get("", response_model=list[ExamResponse])
async def list_exams(
    current_user: User = Depends(get_current_user),
    status: str = "active",
):
    exams = await Exam.find(
        Exam.user_id == current_user.id,
        Exam.status == status,
    ).sort("-created_at").to_list()
    return [_exam_to_response(e) for e in exams]


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(exam: Exam = Depends(get_exam_for_user)):
    return _exam_to_response(exam)


@router.patch("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    body: ExamUpdate,
    exam: Exam = Depends(get_exam_for_user),
):
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    await exam.set(update_data)
    return _exam_to_response(exam)


@router.delete("/{exam_id}", status_code=204)
async def delete_exam(exam: Exam = Depends(get_exam_for_user)):
    # Soft delete — set status = archived, never hard-delete
    await exam.set({"status": "archived", "updated_at": datetime.now(timezone.utc)})


@router.get("/{exam_id}/summary", response_model=ExamSummaryResponse)
async def exam_summary(exam: Exam = Depends(get_exam_for_user)):
    pipeline = [
        {"$match": {"exam_id": exam.id, "is_leaf": True}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "completed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                },
            }
        },
    ]
    results = await Topic.aggregate(pipeline).to_list()
    if not results:
        return ExamSummaryResponse(
            exam_id=str(exam.id), total_leaf_topics=0,
            completed_leaf_topics=0, progress_pct=0.0
        )
    row = results[0]
    total = row["total"]
    completed = row["completed"]
    pct = round((completed / total * 100) if total > 0 else 0.0, 2)
    return ExamSummaryResponse(
        exam_id=str(exam.id),
        total_leaf_topics=total,
        completed_leaf_topics=completed,
        progress_pct=pct,
    )
