# Orbit frontends

Frontend được tổ chức thành một npm workspace với hai ứng dụng React/Vite độc lập:

```text
Frontend/
├── user/       # Chat, assistant, task, calendar, reminder and memory
├── admin/      # Platform dashboard, users và support access
└── shared/     # Design system CSS dùng chung
```

Hai ứng dụng dùng chung FastAPI backend nhưng có entry point, router, biến môi trường, bundle và
local-storage session key riêng. Việc chặn quyền trong frontend chỉ phục vụ trải nghiệm; backend
vẫn kiểm tra JWT, `platform_role`, workspace membership và support grant cho mọi request.

## Cài đặt

Yêu cầu Node.js 20+ và npm:

```powershell
cd Frontend
npm.cmd install
```

## Chạy development

User app, mặc định `http://localhost:5173`:

```powershell
npm.cmd run dev:user
```

Admin app, mặc định `http://localhost:5174`:

```powershell
npm.cmd run dev:admin
```

Sao chép `user/.env.example` thành `user/.env` và `admin/.env.example` thành `admin/.env` nếu cần
đổi backend URL. User app có thể trỏ nút quản trị sang deployment khác bằng
`VITE_ADMIN_APP_URL`; Admin app dùng `VITE_USER_APP_URL` để quay lại ứng dụng người dùng.

## Build

Build cả hai ứng dụng:

```powershell
npm.cmd run build
```

Hoặc build riêng:

```powershell
npm.cmd run build:user
npm.cmd run build:admin
```

Artifact nằm trong `user/dist/` và `admin/dist/`.

## Phân chia trách nhiệm

- `user`: đăng ký/đăng nhập, workspace, chat, AI consent, assistant, task, reminder,
  calendar, memory và profile.
- `admin`: đăng nhập riêng cho platform admin, dashboard, quản lý user và support access có thời
  hạn/owner approval.
- `shared`: CSS nền dùng chung; không chứa business logic hoặc API client.

Không đặt lại route `/admin/*` vào user app. Khi thêm chức năng quản trị mới, thêm page/API vào
`admin`; khi thêm chức năng workspace hoặc dữ liệu cá nhân, thêm vào `user`.
