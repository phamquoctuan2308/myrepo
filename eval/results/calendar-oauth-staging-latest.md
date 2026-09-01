# Google Calendar OAuth - Staging

- Run: `2026-08-29T13:20:25.6325896Z`
- Scope: Calendar access only; Google Sign-In excluded by user request
- Authorization URL: **PASS** (`200`, `accounts.google.com`, Calendar scope and client ID present)
- Calendar client ID: matches the local Calendar setting
- Redirect URI: `https://orbit-backend-xkgq.onrender.com/api/v1/calendar/oauth/callback`
- Callback `postMessage` origin: `https://c3-app-132-auo2.vercel.app` (**PASS**)
- Connection status endpoint: **PASS** (`200`)
- Calendar connected for the evaluation account: **No**
- Interactive Google consent and token exchange: **NOT RUN**

Overall status: **PARTIAL**. The deployed runtime has enough non-empty Calendar OAuth configuration to build the authorization request. A real connection cannot be marked PASS until a user completes Google's login/consent screen.

The Calendar client ID currently equals the Google Sign-In client ID. This is technically usable when the same Google Web OAuth client is intended for both flows; Google Sign-In itself was not exercised.
