"""
Module 3 API Routes — Daily Plans, Check-ins, Feedback.
All endpoints verify exam ownership before acting.
"""
from datetime import date
from fastapi import APIRouter, HTTPException, status
from beanie import PydanticObjectId

from app.api.deps import CurrentUser
from app.models.exam import Exam
from app.models.module_start import ModuleStart
from app.models.daily_plan import DailyPlan
from app.models.daily_report import DailyReport
from app.models.feedback import Feedback
from app.schemas.daily_plan import (
    CheckinRequest, CheckinResponse,
    DailyPlanResponse, FeedbackResponse as FeedbackRespSchema,
    FeedbackHistoryItem,
)
from app.services import daily_service

router = APIRouter(prefix="/daily", tags=["daily"])


# ── Ownership helpers ─────────────────────────────────────────────────────────

async def _get_owned_module_start(module_id: str, user) -> ModuleStart:
    ms = await ModuleStart.get(PydanticObjectId(module_id))
    if not ms:
        raise HTTPException(status_code=404, detail="Module not found")
    exam = await Exam.get(ms.exam_id)
    if not exam or exam.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return ms


async def _get_owned_daily_plan(plan_id: str, user) -> DailyPlan:
    plan = await DailyPlan.get(PydanticObjectId(plan_id))
    if not plan:
        raise HTTPException(status_code=404, detail="Daily plan not found")
    # Verify ownership via module_start
    await _get_owned_module_start(str(plan.module_start_id), user)
    return plan


def _fmt_plan(plan: DailyPlan, has_report: bool = False) -> DailyPlanResponse:
    return DailyPlanResponse(
        id=str(plan.id),
        plan_date=plan.plan_date,
        tasks=plan.tasks,
        carry_over_tasks=plan.carry_over_tasks,
        planned_hours=plan.planned_hours,
        daily_goal=plan.daily_goal,
        status=plan.status,
        has_report=has_report,
    )


def _fmt_feedback(fb: Feedback) -> FeedbackRespSchema:
    return FeedbackRespSchema(
        id=str(fb.id),
        performance_summary=fb.performance_summary,
        pace_status=fb.pace_status,
        risk_level=fb.risk_level,
        suggestions=fb.suggestions,
        motivational_note=fb.motivational_note,
        confidence_display=fb.confidence_display,
        plan_adjusted=fb.plan_adjusted,
        adjustment_summary=fb.adjustment_summary,
        created_at=fb.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/today", response_model=DailyPlanResponse)
async def get_today_plan(module_start_id: str, user: CurrentUser):
    """
    Get today's plan (or lazily generate it if the cron hasn't run yet).
    Returns 404 if the module has no plan day scheduled for today.
    """
    ms = await _get_owned_module_start(module_start_id, user)
    plan = await daily_service.get_or_generate_today_plan(ms.id, user.id)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No plan scheduled for today — module window may have ended.",
        )
    report_exists = await DailyReport.find_one({"daily_plan_id": plan.id}) is not None
    return _fmt_plan(plan, has_report=report_exists)


@router.get("/{daily_plan_id}", response_model=DailyPlanResponse)
async def get_daily_plan(daily_plan_id: str, user: CurrentUser):
    """Get a specific daily plan by ID."""
    plan = await _get_owned_daily_plan(daily_plan_id, user)
    report_exists = await DailyReport.find_one({"daily_plan_id": plan.id}) is not None
    return _fmt_plan(plan, has_report=report_exists)


@router.post("/{daily_plan_id}/checkin", response_model=CheckinResponse)
async def submit_checkin(daily_plan_id: str, body: CheckinRequest, user: CurrentUser):
    """
    Submit end-of-day free-text check-in.
    Triggers Pipeline B: progress extraction → study logs → pace → feedback → replanning.
    """
    plan = await _get_owned_daily_plan(daily_plan_id, user)

    if plan.status in ("completed",):
        report = await DailyReport.find_one({"daily_plan_id": plan.id})
        if report:
            fb = await Feedback.find_one({"daily_report_id": report.id})
            if fb:
                return CheckinResponse(
                    feedback=_fmt_feedback(fb),
                    plan_adjusted=fb.plan_adjusted,
                    adjustment_summary=fb.adjustment_summary,
                )
        raise HTTPException(status_code=409, detail="Check-in already submitted for this day")

    if plan.status == "skipped":
        raise HTTPException(status_code=409, detail="This day was marked as skipped")

    if not body.raw_text or len(body.raw_text.strip()) < 10:
        raise HTTPException(status_code=422, detail="Check-in text must be at least 10 characters")

    feedback = await daily_service.process_checkin(plan, body.raw_text, user.id)

    return CheckinResponse(
        feedback=_fmt_feedback(feedback),
        plan_adjusted=feedback.plan_adjusted,
        adjustment_summary=feedback.adjustment_summary,
    )


@router.get("/{daily_plan_id}/feedback", response_model=FeedbackRespSchema)
async def get_feedback_for_day(daily_plan_id: str, user: CurrentUser):
    """Get mentor feedback for a specific daily plan."""
    plan = await _get_owned_daily_plan(daily_plan_id, user)
    report = await DailyReport.find_one({"daily_plan_id": plan.id})
    if not report:
        raise HTTPException(status_code=404, detail="No check-in submitted for this day yet")
    fb = await Feedback.find_one({"daily_report_id": report.id})
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not yet generated")
    return _fmt_feedback(fb)


@router.patch("/{daily_plan_id}/skip", response_model=DailyPlanResponse)
async def skip_today(daily_plan_id: str, user: CurrentUser):
    """Mark today as skipped. All tasks carry over to tomorrow's plan."""
    plan = await _get_owned_daily_plan(daily_plan_id, user)
    if plan.status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot skip a day with status '{plan.status}'"
        )
    await daily_service.skip_today(plan)
    return _fmt_plan(plan)


# ── Exam-scoped endpoint ──────────────────────────────────────────────────────

@router.get("/exams/{exam_id}/feedback-history", response_model=list[FeedbackHistoryItem])
async def get_feedback_history(exam_id: str, user: CurrentUser):
    """All past feedback entries for an exam, newest first."""
    eid = PydanticObjectId(exam_id)
    exam = await Exam.get(eid)
    if not exam or exam.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    feedbacks = (
        await Feedback.find({"exam_id": eid})
        .sort("-created_at")
        .limit(50)
        .to_list()
    )

    result = []
    for fb in feedbacks:
        report = await DailyReport.get(fb.daily_report_id)
        result.append(FeedbackHistoryItem(
            id=str(fb.id),
            plan_date=report.plan_date if report else date.today(),
            pace_status=fb.pace_status,
            risk_level=fb.risk_level,
            performance_summary=fb.performance_summary,
            suggestions=fb.suggestions,
            motivational_note=fb.motivational_note,
            confidence_display=fb.confidence_display,
            plan_adjusted=fb.plan_adjusted,
            adjustment_summary=fb.adjustment_summary,
            created_at=fb.created_at,
        ))
    return result


# ── Module-scoped endpoint ────────────────────────────────────────────────────

@router.get("/modules/{module_id}/daily-plans", response_model=list[DailyPlanResponse])
async def list_module_daily_plans(module_id: str, user: CurrentUser):
    """List all daily plans for a module (history/calendar view)."""
    ms = await _get_owned_module_start(module_id, user)
    plans = (
        await DailyPlan.find({"module_start_id": ms.id})
        .sort("plan_date")
        .to_list()
    )
    result = []
    for plan in plans:
        has_report = await DailyReport.find_one({"daily_plan_id": plan.id}) is not None
        result.append(_fmt_plan(plan, has_report))
    return result
