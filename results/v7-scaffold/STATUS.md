# v7 status

Branch: `v7-vision-evidence-contracts`  
Design: `docs/V7_DESIGN.md`  
Full GPU archive (episodes, logs, `best.pt`): `results/v7-gpu-archive/`  
Honest diagnosis: `results/v7-gpu-archive/DIAGNOSIS.md`

## Done
- Vision proposal path + Purify authorizer
- Genesis RGB (`genesis_rgb`) closed-loop metrics
- Formal 360 + torch 90 on AMD, fail=0
- Gated unsafe=0; naive unsafe > 0

## Not done (capability bar)
- Active-vision still 0 direct / 0 repair_success (same task outcome as passive)
- Torch head overfits synthetic RGB; on Genesis mostly blocked
- Not a “clearly stronger than V6” contest upgrade yet
