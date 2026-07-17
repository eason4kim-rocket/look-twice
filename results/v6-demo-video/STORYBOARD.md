# v6 demo storyboard (from real episode JSON)

- policy: purify-active
- claims_mode: genesis_rgbd_multi_agent_v6
- device: cuda:0
- mission: True unsafe=False
- route: direct repair_success=True
- observations: 3
- gate receipts: 10
- evidence requests: 2
- RGB-D audits: 3

## Beat sheet
1. Carrier initial front view → low coverage / deny
2. BeliefGap insufficient_roots
3. Scout side views authorized via EvidenceRequestReceipt
4. Independent clear capture roots → Gate admitted
5. Carrier direct corridor cross + delivery

## Motion segments
- carrier → [-0.5, 0.0] reached=True path=1.4206042696359202
- scout → [-0.9, 1.35] reached=True path=0.6195430270729273
- scout → [-0.3, 0.95] reached=True path=0.668583690938429
- carrier → [0.35000000000000003, -0.30000000000000004] reached=True path=0.886481662555926
- carrier → [1.0, -0.30000000000000004] reached=True path=0.6632348162438192
- carrier → [1.7000000000000002, -0.30000000000000004] reached=True path=0.6942157667247272
- carrier → [2.8, 0.0] reached=True path=1.1413962869018872
