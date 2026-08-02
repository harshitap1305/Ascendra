from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends

from app.models.exam import Exam
from app.models.resource import Resource
from app.models.user import User
from app.api.deps import get_current_user, get_exam_for_user
from pydantic import BaseModel


class ResourceCreate(BaseModel):
    type: str
    title: str
    source_name: Optional[str] = None
    url: Optional[str] = None
    total_units: Optional[int] = None
    topic_id: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    exam_id: str
    topic_id: Optional[str]
    type: str
    title: str
    source_name: Optional[str]
    url: Optional[str]
    total_units: Optional[int]


router = APIRouter(tags=["resources"])


@router.post("/exams/{exam_id}/resources", response_model=ResourceResponse, status_code=201)
async def add_resource(
    body: ResourceCreate,
    exam: Exam = Depends(get_exam_for_user),
):
    from beanie import PydanticObjectId
    resource = Resource(
        exam_id=exam.id,
        topic_id=PydanticObjectId(body.topic_id) if body.topic_id else None,
        type=body.type,
        title=body.title,
        source_name=body.source_name,
        url=body.url,
        total_units=body.total_units,
    )
    await resource.insert()
    return ResourceResponse(
        id=str(resource.id),
        exam_id=str(resource.exam_id),
        topic_id=str(resource.topic_id) if resource.topic_id else None,
        type=resource.type,
        title=resource.title,
        source_name=resource.source_name,
        url=resource.url,
        total_units=resource.total_units,
    )


@router.get("/exams/{exam_id}/resources", response_model=list[ResourceResponse])
async def list_resources(exam: Exam = Depends(get_exam_for_user)):
    resources = await Resource.find(Resource.exam_id == exam.id).to_list()
    return [
        ResourceResponse(
            id=str(r.id),
            exam_id=str(r.exam_id),
            topic_id=str(r.topic_id) if r.topic_id else None,
            type=r.type,
            title=r.title,
            source_name=r.source_name,
            url=r.url,
            total_units=r.total_units,
        )
        for r in resources
    ]
