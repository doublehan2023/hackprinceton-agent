from fastapi import APIRouter

from backend.repository import create_annotation
from backend.schemas import AnnotationCreate, AnnotationResponse

router = APIRouter()


@router.post("/annotate", response_model=AnnotationResponse)
def annotate(payload: AnnotationCreate) -> AnnotationResponse:
    annotation_id, training_example_id = create_annotation(payload)
    return AnnotationResponse(annotation_id=annotation_id, training_example_id=training_example_id)
