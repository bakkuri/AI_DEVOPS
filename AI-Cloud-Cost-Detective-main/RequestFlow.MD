## AI Cloud Cost Detective - Request Flow

```
①  User ─·─·─► React ─·─·─► FastAPI Auth ─·─·─► JWT (Amazon RDS PostgreSQL)

②  User selects AWS Resource Group ─·─·─► Python Backend

③  Python ─·─·─► AWS CLI ─·─·─► Fetches all resources in Resource Group

④  Python ─·─·─► FastAPI WebSocket ─·─·─► React (live progress)

⑤  Python ─·─·─► OpenAI API ─·─·─► Cost analysis

⑥  Python ─·─·─► Amazon RDS PostgreSQL ─·─·─► Stores analysis history

⑦  React ◄·─·─·─ Final report with suggestions & AWS CLI fixes
```
