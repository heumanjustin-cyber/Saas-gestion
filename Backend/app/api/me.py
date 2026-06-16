from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

router = APIRouter()


@router.get("/me")
def me(
    current_user=Depends(get_current_user)
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name
    }