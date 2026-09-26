from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.auth_service import auth_service
from backend.logging_config import logger

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    officerName: str = Field(..., description="Full Name", json_schema_extra={"example": "Rahul Sharma"})
    badgeNumber: str = Field(..., description="Official Badge ID / Number", json_schema_extra={"example": "IND-LE-8402"})
    password: str = Field(..., description="Security Passcode", json_schema_extra={"example": "secpass123"})
    department: Optional[str] = Field("Special Crime & Anti-Extortion Unit", description="Department / Unit")
    clearanceLevel: Optional[str] = Field("Level 3: Lead Detective", description="Security Clearance Level")


class LoginRequest(BaseModel):
    badgeNumber: str = Field(..., description="Badge Number or Officer Name", json_schema_extra={"example": "IND-LE-8402"})
    password: str = Field(..., description="Security Passcode", json_schema_extra={"example": "secpass123"})



@router.post("/signup", status_code=status.HTTP_201_CREATED)
@router.post("/register", status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest) -> Dict[str, Any]:
    """Register a new officer with dynamic credentials."""
    try:
        session = auth_service.register(
            officer_name=payload.officerName,
            badge_number=payload.badgeNumber,
            password=payload.password,
            department=payload.department or "Special Crime & Anti-Extortion Unit",
            clearance_level=payload.clearanceLevel or "Level 3: Lead Detective"
        )
        return {
            "success": True,
            "message": f"Officer '{payload.officerName}' registered successfully.",
            "session": session
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during officer registration."
        )


@router.post("/login")
def login(payload: LoginRequest) -> Dict[str, Any]:
    """Authenticate officer credentials and return active session."""
    try:
        session = auth_service.login(
            identifier=payload.badgeNumber,
            password=payload.password
        )
        return {
            "success": True,
            "message": "Authentication successful.",
            "session": session
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during authentication."
        )


@router.get("/users")
def get_registered_users() -> Dict[str, Any]:
    """List registered officers."""
    users = auth_service.list_users()
    return {
        "count": len(users),
        "users": users
    }
