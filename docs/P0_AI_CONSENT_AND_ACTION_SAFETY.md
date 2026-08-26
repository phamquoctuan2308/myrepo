# P0 — AI authorization, event memory, and action safety

P0 establishes the authorization and side-effect boundary. It now uses two policies because a
direct conversation and a managed team group have different governance needs.

## Conversation AI policy

### Group conversation

- One group-wide policy lives on `Conversation.ai_enabled`.
- Only a current conversation participant with `resource_role="manager"` may change it.
- A platform/workspace admin does not implicitly gain access to a private group.
- When enabled, all messages from current authorized group participants form continuous context;
  turns are not removed per author.
- Every participant can read the policy state. A WebSocket `group_ai_policy_changed` event updates
  open clients.
- `ai_policy_version` changes on every real enable/disable transition. It is part of the
  authorization hash used for candidate and HITL staleness checks.

This is an organization-governed product policy. The organization remains responsible for giving
participants visible notice that an external AI provider may process group content.

### Direct conversation

Direct conversations retain the stricter individual policy:

- `granted`: the user may invoke Assistant.
- `contribution_allowed`: messages authored by the user may be reused as AI context.

The two choices remain independent. This avoids silently changing existing direct-chat privacy
semantics while solving the broken-context problem in managed groups.

## Context flow

```text
authenticated requester
  -> current conversation membership
  -> group: Conversation.ai_enabled
     direct: requester.granted + per-author contribution consent
  -> backend queries the selected latest-N request window
  -> AuthorizedMessageView + authorization-scope hash
  -> planner/tool/LLM
  -> response + scope metadata
```

Client-supplied message history is never the authorization source when `conversation_id` exists.
For a group with AI enabled, coverage is complete within the selected immediate request window.
Long-term calendar recall does not depend on making this window unbounded; it uses durable event
candidates described below.

## Durable event extraction

Every new group message passes a cheap event-signal filter. A matching message is processed with a
bounded preceding neighbourhood and the current durable candidates. The model returns exactly one
structured operation:

- `create`: a newly mentioned meeting/event;
- `update`: a reschedule or detail change linked to an existing candidate;
- `cancel`: a cancellation linked to an existing candidate;
- `none`: insufficient evidence.

`EventCandidate` stores title, start/end, location, mentioned attendees, confidence, missing fields,
source message IDs, the authorization hash, and optional Google Calendar event ID. A low-confidence
or malformed model response is ignored. An incomplete candidate is visible but cannot be confirmed.

Suggested creates are updated in place when a later message says, for example, “move it to 10:00”.
Changes to an already confirmed Google event become a separate update/cancel candidate. Confirmation
supersedes the previous canonical candidate or marks it cancelled.

### Historical backfill

`POST /conversations/{id}/event-backfill` processes at most 1–500 messages (default 200) per call in
chronological order. `EventExtractionCursor` makes the scan resumable and prevents every user query
from rereading the entire conversation. Only chunks containing an event signal call the model.
The cursor pauses at the token budget and is reset when the group AI policy changes.

## Human confirmation and lineage

An event candidate is not a calendar event. Only a conversation manager may confirm or dismiss it.
Before confirmation the backend revalidates:

1. the group AI authorization hash;
2. every source message still belongs to an authorized participant;
3. the candidate is still `suggested`;
4. create/update candidates have complete start and end times;
5. update/cancel candidates point to a real confirmed Google event.

Only after those checks does the confirmation endpoint call Google Calendar. Accepting a task never
creates a calendar event or reminder.

## Stale HITL and candidates

Conversation ID and authorization hash are stored in LangGraph state. `/chat/resume` rejects an old
draft if the policy hash changed between proposal and confirmation. A real group policy change also
invalidates all unconfirmed task/event candidates. Confirmed domain records are not silently deleted.

## Current limits

- General summaries/free-form questions still use a bounded 20/50-message immediate window.
- Event extraction uses nearby turns plus durable candidates; it is not general semantic memory.
- Historical scan is intentionally batch-based and must be continued while `has_more=true`.
- Model accuracy still needs a labeled Vietnamese meeting/update/cancellation evaluation set.
- Concurrent external Calendar write + local commit is not yet an atomic distributed transaction;
  production hardening should add an idempotency key in Google Calendar extended properties.
- Direct conversations may still have incomplete context because they retain per-author consent.
