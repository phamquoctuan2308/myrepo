# Lighthouse Staging Evidence

- Run: `2026-08-29T13:15:42.921Z`
- Mode: Lighthouse lab on unauthenticated login pages using system Chrome
- Gates: performance >= 80, accessibility >= 90, LCP <= 2500 ms, CLS <= 0.1

| Surface | Performance | Accessibility | Best practices | SEO | LCP | CLS |
|---|---:|---:|---:|---:|---:|---:|
| User | 61 (FAIL) | 92 (PASS) | 96 | 82 | 6505.108 ms (FAIL) | 0.002921 (PASS) |
| Admin | 82 (PASS) | 83 (FAIL) | 96 | 82 | 3642.232 ms (FAIL) | 0 (PASS) |

INP was not measured because a navigation-only Lighthouse lab run does not provide real-user interaction data.
