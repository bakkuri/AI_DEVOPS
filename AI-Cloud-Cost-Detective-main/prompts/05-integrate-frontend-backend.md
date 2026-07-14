# Prompt 5: Integrate Frontend with Backend (End-to-End)

Connect the React frontend to the FastAPI backend. Wire up WebSocket for live progress, auth for all routes, and history display.

## What to build

### API Integration

- When the user clicks "Run Analysis", send `POST /api/analyze` with the selected AWS Resource Group name and JWT in the `Authorization` header.
- On the backend, validate the JWT on all protected endpoints (`/api/analyze`, `/api/history`, `/api/resource-groups`) using a FastAPI dependency.

### WebSocket Progress

- After triggering analysis, connect to `ws://localhost:8000/ws/progress/{analysis_id}` from React.
- Display each progress message in the `ProgressTracker` component as an animated step list (e.g. listing groups, scanning resources via AWS CLI, AI analysis, storing to RDS).

### History + Reports

- History page fetches from `GET /api/history` with JWT.
- Clicking a past analysis opens the Report page with full details.

### Report Display

- Summary card at the top: total AWS resources scanned, issues found, estimated savings.
- Each issue shows: resource name, AWS resource type (e.g. `AWS::EC2::Instance`), issue type (over-provisioned / unused / misconfigured), severity badge (high = red, medium = yellow, low = green), explanation, and an AWS CLI fix command in a copyable code block.

### Final Testing

- Test the full flow: signup → login → select AWS Resource Group → run analysis → see live progress → view report → check history.
- Verify AWS CLI errors (not installed, not authenticated, invalid resource group) are surfaced clearly in the UI.

Refer to `Architecture.MD` and `RequestFlow.MD`. This covers the full end-to-end flow — steps ① through ⑦.
