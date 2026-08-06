# Look Twice website

This directory contains the complete source for the public Look Twice
experience: the landing page, native demo-video player, Evidence Console,
results, reproduction guide, replay data, and tests.

- [Open the live site](https://eason4kim-rocket.github.io/)
- [Watch the 3:59 demo in the page](https://eason4kim-rocket.github.io/#full-demo)
- [Explore the active and passive replays](https://eason4kim-rocket.github.io/console)
- [Inspect the results](https://eason4kim-rocket.github.io/results)

The site replays recorded, hash-bound evidence. It needs no live GPU, Genesis
process, or private Purify service. The competition run itself used AMD Radeon
and ROCm; the website makes that run easy to inspect in an ordinary browser.

## Run locally

```bash
npm ci
npm test
npm run dev
# open http://localhost:3000
```

## Directory guide

| Path | Contents |
| --- | --- |
| `app/` | Pages, bilingual interface, evidence replay, and 3D visualization |
| `public/data/` | Public replay bundles, result summaries, and source evidence |
| `public/media/` | The complete 3:59 demo, silent 30-second replay, posters, and manifests |
| `tests/` | Rendering, language, data-integrity, media, and evidence-boundary tests |
| `.openai/hosting.json` | Public site deployment configuration |

The default experience is English; the language control switches every public
route to Chinese without changing the underlying evidence.
