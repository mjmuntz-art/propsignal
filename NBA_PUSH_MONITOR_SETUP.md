# NBA PropSignal — automatic push checks without Google Apps Script edits

## What is proven
The `NBA PropSignal - Read-only JSON Feed Probe` workflow completed successfully on GitHub:
- Seven synthetic event tests passed.
- GitHub fetched the existing `?api=card` Google Apps Script JSON endpoint.
- `APPROVED_CURRENT` published slate; detected 10 current plays and 13 graded results on 2026-10-30.

## What this branch adds
1. A GitHub Actions workflow to check the published feed every 30 minutes at minutes 19 and 49 UTC (GitHub may delay scheduled jobs).
2. Semantic change detection for PLAY/LEAN picks, newly locked picks, and new graded outcomes.
3. A compact checkpoint on **separate** `nba-push-checkpoints` branch (public: no tokens, no player data beyond keys/summary).
4. Duplicate protection: event compare with stored checkpoint and OneSignal idempotency keys.
5. A safe off switch: **NO notifications are sent unless `NBA_PUSH_SEND_ENABLED=true`**.

This is intentionally **not** part of Google Apps Script. No new Apps Script trigger is necessary.

## Launch procedure (after review)

**Phase A — dry run**
- Merge the draft PR into `main`. While the GitHub repository variable `NBA_PUSH_SEND_ENABLED` remains absent or false, the scheduled monitor runs **without sending** notifications and establishes a silent baseline.
- Open GitHub **Actions → NBA PropSignal - Automatic Push Monitor → Run workflow**. Verify the `Run offline event tests`, `Fetch feed`, and `Persist checkpoint` steps succeed.
- Check a second run produces zero changes when the public data is unchanged.

**Phase B — secret and delivery**
1. From the OneSignal web dashboard, create or locate the **App-scoped REST API key** for the configured app (App ID `4174a3fe-47af-44be-a68f-257caad1e247`).
2. In GitHub repository **Settings → Secrets and variables → Actions → Secrets → New repository secret**, add:
   - Name: `ONESIGNAL_REST_API_KEY`
   - Value: the OneSignal REST API key.
   Do not post the value in chat, commit it to source control, or put it in a GitHub variable.
3. Verify the subscription has tags `push_nba_prop_enabled=1` and the desired category tags. The frontend sets these when you enable alerts. Without the tags, API sends may match zero devices.
4. In **Settings → Secrets and variables → Actions → Variables → New repository variable**, add:
   - Name: `NBA_PUSH_SEND_ENABLED`
   - Value: `true`.
   **This enables automatic sends! Do not set it until ready.**
5. Trigger the monitor manually or allow scheduled runs. The previously stored baseline prevents first-run spam.

## Turning alerts off quickly
Change `NBA_PUSH_SEND_ENABLED` to `false` or delete that variable in GitHub. This disables outgoing OneSignal API calls but allows the checkpoint to continue tracking current data.

## Supported detection
- **Projections:** new/changed PLAY or LEAN selections on an approved slate; meaningful change to line, status or nearest-unit projection. Minor odds-only updates ignored.
- **Locked:** first transition to locked for a play.
- **Results:** first appearance of graded result for a play in `recent`.
- First observed checkpoint **never sends**. A timestamp-only or unchanged update **never sends**.

## Limitations and safety
- GitHub scheduled jobs may be delayed or skipped. This is an update-notification convenience, not a guaranteed pre-bet timing system.
- Every run uses the **already published JSON feed**; the monitor cannot detect events omitted from that feed.
- Public repository state contains aggregated alert checkpoints and published selection identifiers: no API credentials, no raw personally identifying data.
- This is a draft and has not been tested with real OneSignal API delivery. Use OneSignal dashboard logs after activating.
- The monitoring workflow requests `contents: write` solely to update the dedicated state branch; it does not change `main` or Google Apps Script.
