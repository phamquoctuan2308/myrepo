from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _uuid() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    display_name: Mapped[str]
    role: Mapped[str] = mapped_column(default="user")  # "user" | "admin"
    platform_role: Mapped[str] = mapped_column(default="user")  # "user" | "platform_admin"
    is_active: Mapped[bool] = mapped_column(default=True)
    job_title: Mapped[str] = mapped_column(default="")
    timezone: Mapped[str] = mapped_column(default="Asia/Ho_Chi_Minh")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GoogleIdentity(Base):
    """Link a user to a verified Google account used for authentication."""

    __tablename__ = "google_identities"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    google_sub: Mapped[str] = mapped_column(unique=True, index=True)  # Google's stable subject id
    email: Mapped[str] = mapped_column(default="")  # snapshot at link time, for audit only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship()


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("type IN ('personal', 'organization')", name="ck_workspace_type"),
        CheckConstraint("status IN ('active', 'suspended', 'deleting')", name="ck_workspace_status"),
        CheckConstraint(
            "(type = 'personal' AND personal_owner_user_id IS NOT NULL) OR "
            "(type = 'organization' AND personal_owner_user_id IS NULL)",
            name="ck_workspace_owner_matches_type",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    type: Mapped[str]
    name: Mapped[str]
    slug: Mapped[str | None] = mapped_column(default=None, unique=True)
    personal_owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), default=None, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member', 'guest')", name="ck_workspace_membership_role"),
        CheckConstraint(
            "status IN ('active', 'invited', 'suspended', 'revoked')",
            name="ck_workspace_membership_status",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str]
    status: Mapped[str] = mapped_column(default="active")
    invited_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExternalContact(Base):
    __tablename__ = "external_contacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_external_contact_workspace_email"),
        CheckConstraint("status IN ('invited', 'active', 'revoked')", name="ck_external_contact_status"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str]
    display_name: Mapped[str]
    organization: Mapped[str | None] = mapped_column(default=None)
    linked_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    status: Mapped[str] = mapped_column(default="invited")
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ContactRelationship(Base):
    """A user's private, directional relationship to a person in one workspace."""

    __tablename__ = "contact_relationships"
    __table_args__ = (
        CheckConstraint(
            "((subject_user_id IS NOT NULL) AND (subject_external_contact_id IS NULL)) OR "
            "((subject_user_id IS NULL) AND (subject_external_contact_id IS NOT NULL))",
            name="ck_contact_relationship_exactly_one_subject",
        ),
        CheckConstraint(
            "(subject_kind = 'workspace_user' AND subject_user_id IS NOT NULL "
            "AND subject_external_contact_id IS NULL) OR "
            "(subject_kind = 'external_contact' AND subject_user_id IS NULL "
            "AND subject_external_contact_id IS NOT NULL)",
            name="ck_contact_relationship_kind_matches_subject",
        ),
        CheckConstraint("strength >= 1 AND strength <= 5", name="ck_contact_relationship_strength"),
        CheckConstraint(
            "relationship_type IN ('colleague', 'manager', 'direct_report', 'client', 'partner', "
            "'vendor', 'friend', 'mentor', 'other')",
            name="ck_contact_relationship_type",
        ),
        CheckConstraint(
            "status IN ('suggested', 'active', 'archived', 'rejected')",
            name="ck_contact_relationship_status",
        ),
        CheckConstraint(
            "source IN ('manual', 'ai_suggested', 'imported')",
            name="ck_contact_relationship_source",
        ),
        CheckConstraint(
            "subject_user_id IS NULL OR owner_user_id <> subject_user_id",
            name="ck_contact_relationship_not_self",
        ),
        Index(
            "uq_contact_relationship_workspace_user",
            "workspace_id",
            "owner_user_id",
            "subject_user_id",
            unique=True,
            sqlite_where=text("subject_user_id IS NOT NULL"),
            postgresql_where=text("subject_user_id IS NOT NULL"),
        ),
        Index(
            "uq_contact_relationship_external",
            "workspace_id",
            "owner_user_id",
            "subject_external_contact_id",
            unique=True,
            sqlite_where=text("subject_external_contact_id IS NOT NULL"),
            postgresql_where=text("subject_external_contact_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_kind: Mapped[str]
    subject_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    subject_external_contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("external_contacts.id"), default=None, index=True
    )
    relationship_type: Mapped[str]
    custom_label: Mapped[str | None] = mapped_column(default=None)
    strength: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(default="active")
    source: Mapped[str] = mapped_column(default="manual")
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PeoplePreference(Base):
    """Sparse, private user preferences for people in an organization workspace.

    Interaction metrics are derived from workspace chat/task metadata. Only explicit personal
    choices belong here so users never need to configure every coworker manually.
    """

    __tablename__ = "people_preferences"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "owner_user_id",
            "subject_user_id",
            name="uq_people_preference_workspace_owner_subject",
        ),
        CheckConstraint("owner_user_id <> subject_user_id", name="ck_people_preference_not_self"),
        Index(
            "ix_people_preferences_workspace_owner_pinned",
            "workspace_id",
            "owner_user_id",
            "is_pinned",
        ),
        Index(
            "ix_people_preferences_workspace_owner_follow_up",
            "workspace_id",
            "owner_user_id",
            "follow_up_at",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    private_note: Mapped[str | None] = mapped_column(Text, default=None)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MigrationState(Base):
    __tablename__ = "migration_states"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    migration_key: Mapped[str] = mapped_column(unique=True, index=True)
    migration_version: Mapped[str] = mapped_column(default="workspace_foundation_v1")
    status: Mapped[str]
    error_code: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SupportAccessGrant(Base):
    __tablename__ = "support_access_grants"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    platform_admin_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requested_scope: Mapped[str]
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="requested")
    approved_by_owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SystemConfig(Base):
    """Single-row storage for runtime-editable platform settings."""

    __tablename__ = "system_config"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: "default")
    daily_token_budget: Mapped[int | None] = mapped_column(default=None)
    llm_provider: Mapped[str | None] = mapped_column(default=None)
    model_name: Mapped[str | None] = mapped_column(default=None)
    llm_temperature: Mapped[float | None] = mapped_column(Float, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), default=None, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    actor_type: Mapped[str]
    action: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[str | None] = mapped_column(default=None)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (CheckConstraint("type IN ('direct', 'group')", name="ck_conversation_type"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    type: Mapped[str]  # "direct" | "group"
    name: Mapped[str | None] = mapped_column(default=None)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    # Group conversations use one explicit, manager-controlled AI policy.  This avoids creating
    # syntactically valid but semantically broken context by deleting individual authors' turns.
    # Direct conversations keep the per-user AIPermission model below.
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_policy_version: Mapped[int] = mapped_column(Integer, default=0)
    ai_enabled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    ai_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    participants: Mapped[list["ConversationParticipant"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        CheckConstraint(
            "((user_id IS NOT NULL) AND (external_contact_id IS NULL)) OR "
            "((user_id IS NULL) AND (external_contact_id IS NOT NULL))",
            name="ck_conversation_participant_exactly_one_principal",
        ),
        CheckConstraint(
            "(principal_kind = 'workspace_user' AND user_id IS NOT NULL AND external_contact_id IS NULL) OR "
            "(principal_kind = 'external_contact' AND user_id IS NULL AND external_contact_id IS NOT NULL)",
            name="ck_conversation_participant_kind_matches_principal",
        ),
        CheckConstraint(
            "resource_role IN ('manager', 'participant', 'viewer')",
            name="ck_conversation_participant_resource_role",
        ),
        Index(
            "uq_conversation_participant_user",
            "conversation_id",
            "user_id",
            unique=True,
            sqlite_where=text("user_id IS NOT NULL"),
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_conversation_participant_external",
            "conversation_id",
            "external_contact_id",
            unique=True,
            sqlite_where=text("external_contact_id IS NOT NULL"),
            postgresql_where=text("external_contact_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    principal_kind: Mapped[str] = mapped_column(default="workspace_user")
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    external_contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("external_contacts.id"), default=None, index=True
    )
    resource_role: Mapped[str] = mapped_column(default="participant")
    invited_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])


class AIPermission(Base):
    """Per-user AI choices inside one conversation.

    ``granted`` means this user may invoke the assistant for the conversation.  It deliberately
    does not grant the assistant permission to process messages authored by somebody else.
    ``contribution_allowed`` is the independent author-side consent used by the server-side
    authorized-message resolver.  Keeping the two choices separate avoids treating "I want to use
    AI" as "every participant has allowed my AI to process their content".
    """

    __tablename__ = "ai_permissions"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    granted: Mapped[bool] = mapped_column(default=False)
    contribution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('High', 'Medium', 'Low')", name="ck_task_priority"),
        CheckConstraint(
            "status IN ('suggested', 'pending', 'in_progress', 'completed', 'dismissed', 'invalidated')",
            name="ck_task_status",
        ),
        CheckConstraint("source IN ('manual', 'ai_extracted', 'proactive')", name="ck_task_source"),
        Index("ix_tasks_workspace_owner_status", "workspace_id", "owner_id", "status"),
        Index("ix_tasks_workspace_due_at", "workspace_id", "due_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), default=None, index=True)
    title: Mapped[str]
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    priority: Mapped[str] = mapped_column(default="Medium")  # "High" | "Medium" | "Low"
    status: Mapped[str] = mapped_column(default="suggested")
    # "suggested" | "pending" | "in_progress" | "completed" | "dismissed"
    source: Mapped[str] = mapped_column(default="manual")  # "manual" | "ai_extracted" | "proactive"
    # P0 provenance for unconfirmed AI candidates.  Confirmed domain state may outlive a later
    # source-consent revocation, but a still-suggested candidate is invalidated when its source
    # author revokes contribution processing.
    source_message_ids: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    source_sender_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    consent_scope_hash: Mapped[str | None] = mapped_column(default=None, index=True)
    invalidated_reason: Mapped[str | None] = mapped_column(default=None)
    # Google Calendar event created when an AI-suggested task (proactive/ai_extracted) is
    # accepted - see task_routes._sync_task_to_calendar. NULL for manual tasks and for any
    # AI-suggested task that had no due_at, wasn't accepted yet, or whose owner isn't connected
    # to Google Calendar (sync is best-effort and never blocks Accept).
    calendar_event_id: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    conversation: Mapped["Conversation | None"] = relationship()


class EventCandidate(Base):
    """A consent-scoped calendar fact extracted incrementally from conversation messages.

    Candidates are durable retrieval records, not Google Calendar side effects.  A conversation
    manager must explicitly confirm a complete candidate before an external event is created.
    """

    __tablename__ = "event_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('suggested', 'confirmed', 'superseded', 'dismissed', 'cancelled', 'invalidated')",
            name="ck_event_candidate_status",
        ),
        CheckConstraint(
            "operation IN ('create', 'update', 'cancel')",
            name="ck_event_candidate_operation",
        ),
        Index("ix_event_candidates_conversation_status", "conversation_id", "status"),
        Index("ix_event_candidates_workspace_start", "workspace_id", "start_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    operation: Mapped[str] = mapped_column(default="create")
    target_candidate_id: Mapped[str | None] = mapped_column(ForeignKey("event_candidates.id"), default=None, index=True)
    title: Mapped[str]
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    location: Mapped[str | None] = mapped_column(default=None)
    attendees: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="suggested")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    authorization_scope_hash: Mapped[str] = mapped_column(index=True)
    calendar_event_id: Mapped[str | None] = mapped_column(default=None, index=True)
    calendar_owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    invalidated_reason: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class EventExtractionCursor(Base):
    """Resumable cursor for bounded historical event extraction."""

    __tablename__ = "event_extraction_cursors"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    last_message_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_message_id: Mapped[str | None] = mapped_column(default=None)
    processed_message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(default="idle")
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ConversationRollingSummary(Base):
    """Consent-scoped, incrementally-maintained cumulative summary of one Conversation (1-1 or
    group human chat), so the agent can answer free-form questions spanning months even though the
    live per-request context window (consent_service.build_authorized_message_view) only covers
    the most recent request.context_limit messages. Built by conversation_summary_service.heartbeat
    from messages whose sender is currently in the conversation's readable set
    (proactive_service._permission_scope) - never from a participant who hasn't consented.

    Distinct from AssistantThread.session_summary/MemoryEpisode, which cover the standalone
    /assistant page (conversation_id=None) and already existed before this table.
    """

    __tablename__ = "conversation_rolling_summaries"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    last_message_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_message_id: Mapped[str | None] = mapped_column(default=None)
    processed_message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(default="idle")  # idle|running|failed
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    # Set whenever a participant's contribution_allowed is revoked (or they leave/are removed from
    # an AI-enabled group) so the next heartbeat pass rebuilds the summary from scratch using only
    # currently-consenting senders, instead of letting already-baked prose from a revoked
    # participant keep being replayed into every future agent turn indefinitely. See
    # chat_service.set_ai_permission and the group participant-removal path.
    needs_reset: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), default=None, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    provider: Mapped[str]
    model: Mapped[str]
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class AgentThread(Base):
    __tablename__ = "agent_threads"
    __table_args__ = (
        Index("ix_agent_threads_owner_last_active", "owner_id", "last_active_at"),
        Index("ix_agent_threads_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "memory_type IN ('preference', 'relationship', 'episodic', 'semantic', "
            "'fact', 'entity', 'decision', 'open_loop', 'knowledge', 'procedural')",
            name="ck_memory_type",
        ),
        CheckConstraint(
            "sensitivity IN ('normal', 'sensitive')",
            name="ck_memory_sensitivity",
        ),
        Index("ix_memories_workspace_owner_created", "workspace_id", "owner_id", "created_at"),
        Index("ix_memories_owner_type_expiry", "owner_id", "memory_type", "expires_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(default="Preference")  # "Work" | "Preference" | "People" | ...
    title: Mapped[str]
    detail: Mapped[str] = mapped_column(default="")
    # memory_type describes how recall/consolidation should treat the record: auto-extracted
    # memories from conversations use preference/relationship/episodic/semantic; memories the
    # user explicitly asks Orbit to remember (remember_fact tool) use fact/entity/decision/
    # open_loop/knowledge - see ck_memory_type above for the full allowed set.
    memory_type: Mapped[str] = mapped_column(default="semantic", index=True)
    status: Mapped[str] = mapped_column(default="active", index=True)
    source_type: Mapped[str] = mapped_column(default="manual")
    source_id: Mapped[str | None] = mapped_column(default=None)
    source_thread_id: Mapped[str | None] = mapped_column(default=None, index=True)
    source_conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), default=None, index=True)
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    consent_scope_hash: Mapped[str | None] = mapped_column(default=None, index=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    sensitivity: Mapped[str] = mapped_column(default="normal")
    user_confirmed: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(default="", index=True)
    # JSON keeps the deployment PostgreSQL-only without making pgvector a hard dependency. The
    # retrieval service can later move this to pgvector without changing the API or memory schema.
    embedding: Mapped[list | None] = mapped_column(JSON, default=None)
    embedding_model: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped["User"] = relationship()


class CalendarSyncState(Base):
    """Per-workspace Google Calendar incremental sync cursor."""

    __tablename__ = "calendar_sync_state"

    workspace_id: Mapped[str] = mapped_column("id", ForeignKey("workspaces.id"), primary_key=True)
    sync_token: Mapped[str | None] = mapped_column(default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AssistantThread(Base):
    """One row per Personal AI Assistant chat session (/assistant page) - lets a user browse past
    sessions ("Gần đây" sidebar). Distinct from Conversation (1-1/group human chat) and from the
    LangGraph checkpointer's own Postgres tables: those hold the full message state per thread_id
    but have no owner_id column and no title/preview concept, so they can't answer "which threads
    belong to this user" on their own - this table is the missing owner_id -> thread_id index, kept
    in sync from src/api/routes.py (chat()/resume_chat()) whenever a turn completes. Only chat()
    calls with conversation_id=None create a row here - AIPanel's embedded quick actions/Ask Orbit
    (always conversation_id-scoped) are a different, unrelated flow and must not show up in this
    list."""

    __tablename__ = "assistant_threads"

    thread_id: Mapped[str] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    title: Mapped[str]  # fixed at creation from the first message - like a conversation name, never edited after
    preview: Mapped[str] = mapped_column(default="")
    session_summary: Mapped[str] = mapped_column(Text, default="")
    compacted_message_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_memory_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped["User"] = relationship()


class MemoryEpisode(Base):
    """A compact, chronological account of one completed slice of an assistant thread.

    Episodes are evidence-backed summaries, not instructions. Durable facts extracted from an
    episode are written as ``Memory(status='pending_review')`` until the user approves them.
    """

    __tablename__ = "memory_episodes"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    thread_id: Mapped[str | None] = mapped_column(default=None, index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), default=None, index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    decisions: Mapped[list] = mapped_column(JSON, default=list)
    open_loops: Mapped[list] = mapped_column(JSON, default=list)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list | None] = mapped_column(JSON, default=None)
    embedding_model: Mapped[str | None] = mapped_column(default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped["User"] = relationship()


class GoogleCalendarCredential(Base):
    """Encrypted per-user OAuth credential and incremental sync cursor."""

    __tablename__ = "google_calendar_credentials"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    google_email: Mapped[str] = mapped_column(default="")
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    access_token_enc: Mapped[str | None] = mapped_column(Text, default=None)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    scopes: Mapped[str] = mapped_column(default="")
    sync_token: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship()


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled', 'fired', 'cancelled')", name="ck_reminder_status"),
        CheckConstraint("source IN ('manual', 'agent', 'proactive')", name="ck_reminder_source"),
        Index("ix_reminders_workspace_owner_status", "workspace_id", "owner_id", "status"),
        Index("ix_reminders_workspace_fire_at", "workspace_id", "fire_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str]
    message: Mapped[str] = mapped_column(default="")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="scheduled")  # "scheduled" | "fired" | "cancelled"
    source: Mapped[str] = mapped_column(default="manual")  # "manual" | "agent" | "proactive"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped["User"] = relationship()
