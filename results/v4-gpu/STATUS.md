# Look Twice v4 W7900D status (honest)

## Completed on AMD Radeon PRO W7900D (Genesis 1.1.2, ROCm 7.2)

1. CPU/Go contracts verified on cloud image.
2. Single-env Genesis closed-loop smoke with GateReceipts.
3. 8-profile × 1 seed Genesis smoke (purify-active).
4. Skid-steer motion acceptance **failed** (14/40 viewpoint trials); formal path demoted to **kinematic**.
5. Formal calibration collection: 336/350 seeds retained after multi-viewpoint retry; partial split fitted with `--allow-nonstandard-split` and `PARTIAL_SPLIT.txt`.
6. GPU evidence benchmark (`batch 1/8/32/128`, warmup 20 / timed 100) when present under `bench/`.
7. **Genesis smoke matrix 6×8×2 = 96** completed with fitted calibration; summaries under `smoke-genesis/summary/`.
8. **Formal closed-loop 6×8×20 = 960** started on the live instance with resume-safe atomic JSON (`outputs/v4-formal-genesis` on GPU). Counts will grow while the GPU is left running.

## Not claimed

- Full 960 formal completion until the cloud matrix finishes and is re-synced.
- Skid-steer formal physics validation (explicitly demoted).
- Full promotion-threshold certification on locked test N=960 (smoke N is too small for CI claims).

## GPU policy

Instance left **running** for formal matrix continuation (user objective).
