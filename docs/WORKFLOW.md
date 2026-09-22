# Guided workflow plans

A supervisor may propose structured JSON, but Company HQ only imports it after explicit preview and import. Plans require a goal and 1–20 uniquely keyed DAG steps with known owners, dependency keys, and acceptance checks. Import creates canonical TaskStore tasks and dependency links; it never begins execution or marks work complete. Apply is idempotent per team and client request ID through a private receipt.

API contracts: `POST /api/plans/{team}/preview` receives `{plan,members}` and returns the ordered card. `POST /api/plans/{team}/apply` receives `{plan,members,requestId}` and returns the card with `taskIDs`, statuses, and dependency IDs.
