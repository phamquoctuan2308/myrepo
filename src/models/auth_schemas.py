from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class AdminRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=80)
    bootstrap_key: str


class UserPublic(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    platform_role: Literal["user", "platform_admin"]
    job_title: str = ""
    timezone: str = "Asia/Ho_Chi_Minh"
    preferences: dict = Field(default_factory=dict)


class UserPreferencesUpdate(BaseModel):
    default_reminder_lead_minutes: Literal[15, 30, 60] = 30
    desktop_notifications: bool = True
    ai_suggestion_alerts: bool = False
    permission_scope: Literal["latest_20", "latest_50", "unread"] = "latest_20"


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    job_title: str | None = Field(default=None, max_length=80)
    timezone: Literal["Asia/Ho_Chi_Minh", "Europe/London", "America/New_York"] | None = None
    preferences: UserPreferencesUpdate | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserPublic


class WebSocketTicketOut(BaseModel):
    ticket: str
    expires_in: Literal[60] = 60
