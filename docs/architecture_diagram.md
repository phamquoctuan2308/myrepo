# Architecture Diagram

> Đây là sơ đồ rút gọn canonical cho deliverable “System diagram + Component descriptions”.
> Kiến trúc và boundary đầy đủ nằm trong [ARCHITECTURE.md](ARCHITECTURE.md); phần Workspace mở rộng nằm trong [workspace-development/](workspace-development/README.md).

## System Overview

```mermaid
graph TB
    subgraph Frontend["Frontend — React + Vite (2 app riêng)"]
        UserApp["Frontend/user/ — cổng 5173<br/>Chat, AI Assistant, Tasks, Calendar, Reminders, Memory, Profile"]
        AdminApp["Frontend/admin/ — cổng 5174<br/>Dashboard, Users, Conversations, User data,<br/>AI Management, AI Usage, Audit Log"]
        WSClient[WebSocket client — mỗi app tự kết nối riêng]
    end

    subgraph Backend["Backend — FastAPI (1 app duy nhất)"]
        AuthAPI["/api/v1/auth, /auth/admin/*"]
        ChatAPI["/api/v1/conversations, /messages"]
        AdminAPI["/api/v1/admin/*"]
        AgentAPI["/api/v1/chat, /chat/resume, /assistant/threads"]
        DataAPI["/api/v1/tasks, /calendar, /reminders, /memories, /usage"]
        WS["/api/v1/ws"]
        Agent["LangGraph Agent — planner + 11 tool"]
        LLM["LLM Service — get_llm()"]
        Scheduler["APScheduler — reminders + calendar poll"]
        Proactive[proactive_service]
        Audit[audit_service]
    end

    subgraph Data["Data Layer"]
        DB[(PostgreSQL — app data + LangGraph checkpoint + APScheduler jobstore)]
        Google[Google Calendar API]
        LLMProvider[Gemini / Groq / OpenAI]
    end

    UserApp -->|HTTP/REST| AuthAPI
    UserApp -->|HTTP/REST| ChatAPI
    UserApp -->|HTTP/REST| AgentAPI
    UserApp -->|HTTP/REST| DataAPI
    AdminApp -->|HTTP/REST| AuthAPI
    AdminApp -->|HTTP/REST| AdminAPI
    WSClient <-->|WebSocket| WS

    AgentAPI --> Agent
    Agent -.->|checkpoint theo thread_id| DB
    Agent --> LLM --> LLMProvider
    Agent --> Google

    ChatAPI -->|tin nhắn mới| Proactive
    WS -->|tin nhắn mới| Proactive
    Proactive --> LLM
    Proactive -->|task gợi ý| DB

    Scheduler -->|poll thay đổi| Google
    Scheduler -->|bắn reminder| DB
    Scheduler -.->|broadcast| WS

    AdminAPI --> Audit --> DB
    AuthAPI --> DB
    ChatAPI --> DB
    DataAPI --> DB
    WS --> DB
```

## Agent Flow (LangGraph)

```mermaid
graph LR
    START --> planner
    planner -->|có tool call| tools
    planner -->|trả lời thẳng / lỗi| END
    tools -->|tool cần xác nhận<br/>calendar CRUD, create_reminder| planner
    tools -->|tool terminal<br/>summarize, extract_tasks, search_messages| END
    tools -.->|interrupt chờ người dùng| Resume["POST /chat/resume"]
    Resume --> planner
```

## Component Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend (user) | React 18, Vite, React Router, Bootstrap 5 | UI cho người dùng cuối — chat, AI assistant, task/lịch/nhắc việc/memory/hồ sơ |
| Frontend (admin) | React 18, Vite (app Vite riêng, không chung router với app user) | UI quản trị hệ thống — user, hội thoại, cấu hình AI, chi phí token, audit log |
| Backend | FastAPI (async), 1 process duy nhất phục vụ cả 2 frontend | REST API + WebSocket gateway, xác thực JWT/bcrypt |
| Agent orchestration | LangGraph | Vòng lặp planner ⇄ tool, human-in-the-loop qua `interrupt()`, checkpoint bền vững theo `thread_id` |
| LLM | Google Gemini / Groq / OpenAI (đổi qua `LLM_PROVIDER`, hoặc qua UI "AI Management" lúc đang chạy) | Sinh nội dung tóm tắt/trích task/trả lời chat |
| Database | PostgreSQL (bắt buộc — không còn hỗ trợ SQLite) qua SQLAlchemy async | Toàn bộ dữ liệu app + checkpoint LangGraph + jobstore APScheduler trong cùng 1 database |
| Realtime | WebSocket thuần (FastAPI), 1 kênh dùng chung cho chat/reminder/task/calendar/usage-alert | Đẩy sự kiện tới đúng người liên quan, không polling |
| Scheduler | APScheduler + `SQLAlchemyJobStore` | Bắn reminder đúng giờ, poll thay đổi Google Calendar định kỳ — cả hai bền vững qua restart |
| External API | Google Calendar API (OAuth per-user), Google/Groq/OpenAI LLM API | Lịch cá nhân thật + suy luận AI |
| Vector Store | Không triển khai cho Personal Agent (quyết định có chủ đích) | Memory hiện dùng PostgreSQL/checkpoint và các service memory — xem [ARCHITECTURE.md](ARCHITECTURE.md) |

Chi tiết Data Flow, Security và boundary: xem [ARCHITECTURE.md](ARCHITECTURE.md). Đối chiếu yêu cầu và bằng chứng: xem [Traceability Matrix](../eval/TRACEABILITY_MATRIX.md).
