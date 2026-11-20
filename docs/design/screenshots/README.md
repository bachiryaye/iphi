# Application captures

The Help captures were refreshed on 20 November 2026 from the actual public `/help`
page implementing the novice-guide update in [ADR 0027](../../adr/0027-bilingual-help.md).
They show the source in this change, with IBM Plex Sans loaded, 16 px reading text
at the default root size and 26 px line height. No authentication, API mocks,
private data or image editing was used. The desktop contents are initially open;
the tablet contents are initially collapsed. The exercise capture preserves that
collapsed choice after widening the viewport, in the dark theme.

The unchanged Overview and sign-in captures come from source `812a307`, archived by
[CI 44580461936](https://github.com/bachiryaye/iphi/actions/runs/44580461936), without
mocked telemetry. The dashboard waits for actual baseline rule evaluations:

- [French Overview, light, 1440 px](finalization-overview-fr-light-1440.png)
- [English beginner help, light, 1440 px](finalization-help-en-light-1440.png)
- [French beginner help, dark, 768 px](finalization-help-fr-dark-768.png)
- [French numbered exercise, dark, 1440 px](novice-help-fr-exercise-dark-1440.png)
- [French sign-in, light, 1440 px](finalization-login-fr-light-1440.png)

Run `make demo IPHI_LLM_PROVIDER=none`, then:

```sh
cd frontend
IPHI_E2E_URL=http://127.0.0.1:8081 pnpm exec playwright test e2e/help.capture.ts --project=screenshots
```

The capture workflow uses explicit authenticated/empty session state, checks the page heading and language, and verifies that the sign-in password field is empty. The dashboard capture checks that state labels fit their cells. Screenshots contain simulated observations only.

The extra exercise capture uses French on `/help#scenarios`, a 1440 × 900 viewport
and the dark theme. Navigate to that chapter from the guide before capturing with
Playwright CLI. It shows actual instructions, without replacing the guide text.
Local checks also verified no horizontal overflow at 320 px and at 200% text size
(32 px / 52 px), plus focus on the selected chapter.

Older files, including `us-XX-*` and the original unprefixed dashboard images, are retained as milestone evidence. Their chrome may predate the current language selector and help. `make screenshots` explicitly regenerates both the original dashboard views and the current help/sign-in captures from the demo stack; it changes the demo simulation state.
