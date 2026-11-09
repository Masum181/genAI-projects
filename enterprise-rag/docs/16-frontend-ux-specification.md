# 16. Frontend and UX Specification

## 1. UI principles
The initial frontend uses FastAPI Jinja2 + HTMX for a minimal and operationally reliable interface. The design prioritizes clarity, permissions awareness, and low latency for enterprise use.

## 2. Screens and flows

### Login and registration
- Purpose: Authenticate users and create tenant accounts.
- Roles: all.
- Components: form fields, tenant selector, validation message, MFA prompts for privileged users.

### Organization dashboard
- Purpose: summarize usage and tenant health.
- Roles: super admin, organization admin.
- Components: KPI cards, recent activity, document counts, active users.

### Employee dashboard
- Purpose: provide quick access to authorized knowledge and recent conversations.
- Roles: employee, manager.
- Components: search, recent docs, favorites, chat shortcuts.

### Document library
- Purpose: browse documents and metadata.
- Roles: all authorized users.
- Components: table, filters, status badges, document action menu.

### Document upload
- Purpose: upload and monitor ingestion.
- Roles: organization admin and department manager with permissions.
- Components: file picker, metadata form, upload progress, status summary.

### Ingestion status
- Purpose: show processing progress and failures.
- Roles: uploader/admin.
- Components: job lifecycle, retry counts, error messages.

### Document permissions
- Purpose: assign read/write/admin rights by department or user.
- Roles: organization admin, department manager with authority.

### Chat interface
- Purpose: ask questions, see answers, and review citations.
- Roles: employees and managers with access.
- Components: prompt box, loading state, citation panel, streaming answer view.

### Citation viewer
- Purpose: inspect source document, page, and excerpt with answer traceability.
- Roles: all users with answer access.

### Conversation history
- Purpose: revisit previous questions and answers.
- Roles: employee, manager, admin.

### Feedback interface
- Purpose: collect thumbs-up/down and issue notes.
- Roles: all answerers.

### Admin dashboard
- Purpose: track usage, org metrics, current jobs, and safe admin actions.
- Roles: super admin, org admin.

## 3. UX states
Every screen must support:
- loading state,
- empty state,
- validation state,
- error state,
- success state.

## 4. Related documents
- [06-api-design.md](./06-api-design.md)
- [17-business-workflows.md](./17-business-workflows.md)
- [15-deployment-and-devops.md](./15-deployment-and-devops.md)
