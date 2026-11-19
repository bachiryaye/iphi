# Application captures

Current finalization captures come from the running application on source `812a307`, archived by [CI 44580461936](https://github.com/bachiryaye/iphi/actions/runs/44580461936), without mocked telemetry. The dashboard waits for actual baseline rule evaluations:

- [French Overview, light, 1440 px](finalization-overview-fr-light-1440.png)
- [English beginner help, light, 1440 px](finalization-help-en-light-1440.png)
- [French beginner help, dark, 768 px](finalization-help-fr-dark-768.png)
- [French sign-in, light, 1440 px](finalization-login-fr-light-1440.png)

Run `make demo IPHI_LLM_PROVIDER=none`, then:

```sh
cd frontend
IPHI_E2E_URL=http://127.0.0.1:8081 pnpm exec playwright test e2e/help.capture.ts --project=screenshots
```

The capture workflow uses explicit authenticated/empty session state, checks the page heading and language, and verifies that the sign-in password field is empty. The dashboard capture checks that state labels fit their cells. Screenshots contain simulated observations only.

Older files, including `us-XX-*` and the original unprefixed dashboard images, are retained as milestone evidence. Their chrome may predate the current language selector and help. `make screenshots` explicitly regenerates both the original dashboard views and the current help/sign-in captures from the demo stack; it changes the demo simulation state.
