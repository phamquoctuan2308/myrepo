import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.auth import google_oauth
from src.auth.dependencies import get_current_user
from src.auth.security import create_access_token, create_websocket_ticket, hash_password, verify_password
from src.config import get_settings
from src.db.models import GoogleIdentity, User
from src.db.session import get_db
from src.models.auth_schemas import (
    AdminRegisterRequest,
    AuthResponse,
    ChangePasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserPublic,
    WebSocketTicketOut,
)
from src.services.audit_service import record_audit_event
from src.services.workspace_service import create_personal_workspace

router = APIRouter()


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        platform_role=user.platform_role,
        job_title=user.job_title,
        timezone=user.timezone,
        preferences=user.preferences,
    )


def _initial_role_for(email: str) -> str:
    """The first account registered with INITIAL_ADMIN_EMAIL (any auth method) bootstraps as
    admin - shared by /register and /google so the rule isn't duplicated/drifting between them."""
    initial_admin_email = get_settings().initial_admin_email.strip().lower()
    return "admin" if initial_admin_email and email.lower() == initial_admin_email else "user"


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserPublic:
    normalized_email = str(request.email).lower()
    existing = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    role = _initial_role_for(normalized_email)
    user = User(
        email=normalized_email,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        role=role,
        platform_role="platform_admin" if role == "admin" else "user",
    )
    db.add(user)
    await db.flush()
    await create_personal_workspace(db, user)
    await db.commit()
    await db.refresh(user)

    return _to_public(user)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = (await db.execute(select(User).where(User.email == request.email.lower()))).scalar_one_or_none()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been disabled")

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Sign in (or sign up on first use) with a Google ID token from the frontend's <GoogleLogin/>
    button. One endpoint handles both login and signup transparently - there's nothing to
    distinguish client-side, same as the button itself is identical on /login and /register."""
    try:
        claims = await run_in_threadpool(google_oauth.verify_google_id_token, request.id_token)
    except google_oauth.GoogleTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token") from None

    google_sub = claims["sub"]
    email = claims.get("email", "").lower()
    email_verified = claims.get("email_verified", False)
    if not email or not email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified")

    identity = (
        await db.execute(select(GoogleIdentity).where(GoogleIdentity.google_sub == google_sub))
    ).scalar_one_or_none()

    if identity is not None:
        user = await db.get(User, identity.user_id)
    else:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None and not email_verified:
            # Don't silently attach a Google identity to an existing account on the strength of an
            # email Google itself won't vouch for - that would be an account-takeover vector.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email not verified by Google; sign in with your password instead",
            )
        if user is None:
            role = _initial_role_for(email)
            user = User(
                email=email,
                # Unusable, never-shared password - password_hash stays NOT NULL without adding a
                # nullable column to `users`. Password login on this account will just always 401
                # (correct: nobody ever set a password for it) until/unless they set one later.
                password_hash=hash_password(secrets.token_urlsafe(32)),
                display_name=claims.get("name") or email.split("@")[0],
                role=role,
                platform_role="platform_admin" if role == "admin" else "user",
            )
            db.add(user)
            await db.flush()
            await create_personal_workspace(db, user)
        db.add(GoogleIdentity(user_id=user.id, google_sub=google_sub, email=email))
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been disabled")

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.post("/admin/register", response_model=AuthResponse)
async def register_admin(body: AdminRegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Create the first administrator from the separate Frontend/admin app's one-time setup
    screen, gated by ADMIN_BOOTSTRAP_KEY. Not a replacement for INITIAL_ADMIN_EMAIL (still works
    unchanged via /register) - this exists for deployments that would rather gate the first admin
    behind a secret than pre-decide an email address. Once an admin exists, additional admins are
    promoted from the Admin > Users screen instead."""
    bootstrap_key = get_settings().admin_bootstrap_key
    if not bootstrap_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin bootstrap is not configured"
        )
    if not secrets.compare_digest(body.bootstrap_key, bootstrap_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin bootstrap key")

    admin_exists = (await db.execute(select(User.id).where(User.role == "admin").limit(1))).scalar_one_or_none()
    if admin_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An admin account already exists. Ask an existing admin to promote another account.",
        )

    normalized_email = str(body.email).lower()
    existing = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=normalized_email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role="admin",
        platform_role="platform_admin",
    )
    db.add(user)
    await db.flush()
    await create_personal_workspace(db, user)
    await record_audit_event(
        db,
        actor=user,
        action="auth.admin_account_registered",
        target_type="user",
        target_id=user.id,
        workspace_id=None,
        metadata={"method": "bootstrap_key"},
    )
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.post("/admin/login", response_model=AuthResponse)
async def admin_login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """Same credential check as /login, plus a role check - used by the separate Frontend/admin
    app so a non-admin account can't get a session there even with a correct password."""
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been disabled")

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return _to_public(current_user)


@router.post("/ws-ticket", response_model=WebSocketTicketOut)
async def websocket_ticket(current_user: User = Depends(get_current_user)) -> WebSocketTicketOut:
    return WebSocketTicketOut(ticket=create_websocket_ticket(current_user.id))


@router.patch("/me", response_model=UserPublic)
async def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    updates = request.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return _to_public(current_user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    current_user.password_hash = hash_password(request.new_password)
    await db.commit()
