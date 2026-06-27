# Bank Presets

MoneyLeak AI includes an Indian bank preset registry with automatic detection and manual override during upload.

Supported presets:

| Key | Bank |
|---|---|
| `sbi` | SBI |
| `hdfc` | HDFC Bank |
| `icici` | ICICI Bank |
| `axis` | Axis Bank |
| `kotak` | Kotak Mahindra Bank |
| `canara` | Canara Bank |
| `union` | Union Bank |
| `paytm` | Paytm Payments Bank |
| `generic` | Generic fallback parser |

The parser reports:

- detected bank key and display name
- detection confidence
- detection source: `auto` or `manual`
- credit-card hints such as posting date, due date, minimum amount due, total amount due, late fee, finance charge, and interest markers

Unknown formats fall back to the generic parser and return warnings or structured errors instead of crashing.

