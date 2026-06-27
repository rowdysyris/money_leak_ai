# MoneyLeak AI API

All business endpoints return the standard envelope.

Success:

```json
{ "success": true, "data": {}, "warnings": [] }
```

Error:

```json
{ "success": false, "error": { "code": "ERROR_CODE", "message": "Human readable message", "details": {} } }
```

## Public Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Basic process and database visibility. |
| GET | `/ready` | Deployment readiness with database connectivity. |
| POST | `/api/auth/register` | Create user and return JWT. |
| POST | `/api/auth/login` | Authenticate and return JWT. |

## Authenticated Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/auth/me` | Current user profile. |
| GET | `/api/statements/bank-presets` | Supported parser presets. |
| GET | `/api/statements` | List the current user's statements and processing state. |
| GET | `/api/statements/{statement_id}` | Read one owned statement and its processing state. |
| POST | `/api/statements/upload` | Upload one statement. |
| POST | `/api/statements/upload-multiple` | Upload and merge multiple statements. |
| GET | `/api/transactions` | Paginated user transactions. |
| PATCH | `/api/transactions/{id}/category` | Correct one transaction and save memory. |
| GET | `/api/transactions/category-rules` | List saved merchant rules. |
| POST | `/api/transactions/category-rules` | Create/update a merchant rule. |
| POST | `/api/transactions/category-rules/{id}/apply` | Apply a rule to existing transactions. |
| DELETE | `/api/transactions/category-rules/{id}` | Delete a saved rule. |
| GET | `/api/dashboard/summary` | Dashboard summary. |
| GET | `/api/insights/*` | Leaks, subscriptions, duplicates, month comparison, alerts. |
| GET | `/api/insights/merchant-addiction` | Merchant concentration and repeat-spend risk. |
| POST | `/api/budget/setup` | Create/update budget. |
| GET | `/api/budget/status` | Budget progress. |
| GET | `/api/reports/download/pdf` | PDF report. |
| GET | `/api/reports/download/csv` | CSV export. |
| GET | `/api/reports/download/excel` | Excel report. |
| POST | `/api/agents/analyze` | Start the user-scoped analysis graph. |
| GET | `/api/agents/status/{run_id}` | Read an owned analysis run. |
| POST | `/api/agents/recommend` | Generate resilient recommendations. |
| POST | `/api/rag/query` | Query user-scoped financial memory. |

## Manual column mapping

`POST /api/statements/upload` accepts multipart fields `file`, optional `bank_preset`, and optional `column_mapping`. The mapping is a JSON object whose values must exactly match columns in the uploaded file:

```json
{
  "date": "Transaction Date",
  "description": "Narration",
  "debit": "Withdrawal Amount",
  "credit": "Deposit Amount",
  "balance": "Closing Balance"
}
```

An `amount` column can replace separate `debit` and `credit` columns. When automatic mapping confidence is below `0.7`, the API returns `requires_column_mapping: true` without persisting a statement; the client resubmits the same file with the confirmed mapping.
