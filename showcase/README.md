# Look Twice Evidence Console

Version-neutral replay website for the Look Twice competition release. It reads
only `ReleaseProfile v1` and `EpisodeBundle v1`; candidate-specific runtime JSON
is converted by an adapter before entering `public/data`.

```bash
npm install
npm run dev
```

The public experience is replay-first and has no Genesis, ROCm, GPU, or live
Purify dependency.
