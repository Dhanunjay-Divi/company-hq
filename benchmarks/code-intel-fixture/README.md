# Code-intelligence benchmark fixture

Synthetic fixture only. The expected relationships are:

- `get_report` calls `authorize_session`.
- `authorize_session` calls `validate_token` and `check_permission`.
- `export_report` calls `get_report`.
- `invoiceTotal` calls `calculateTax`.
- `renderInvoice` calls `invoiceTotal`.

No secrets, provider credentials, or model calls are required.
