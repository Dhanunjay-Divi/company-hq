# 2026-09-25 — Recent chats and desktop icon

The sidebar now orders conversations by durable local activity. A teammate stays
beneath its parent chat, while activity in that branch moves the project group
up. The overview API reads only timestamps from the team config, profile and
private transcript database; it does not open or return transcript text. The UI
moves a chat up after a successful send and refreshes the list while visible.

The macOS app now bundles the Company HQ icon with a centered D monogram. The
same PNG and ICNS are in source, and the unsigned local app and DMG were rebuilt.
The public `v0.1.0` preview has a pinned curl installer that verifies the DMG
checksum and installs into the user's Applications folder without `sudo`.

Verification: the full model-free check passed 315 integration tests, 12
JavaScript checks, source-bundle and portability checks. The browser acceptance
flow passed using synthetic provider transport. A focused API test verifies
that accepted message activity moves a chat to the top without exposing text;
the hierarchy check verifies nested ordering. The first API test used the wrong
fixture transcript root; inspection of live state exposed the actual
`runtime/transcripts` path, and both code and test were corrected. The first
DMG attempt left a temporary image mounted; it was detached and packaging
subsequently succeeded.

The local source server at port 59533 was restarted with the change. The app
was built locally, not installed into Applications or signed/notarized. No
model turn was started for this round, so there are no meaningful model-token
measurements. Native account access and a signed release remain unverified.
