# v6 matrix final status (auto)

- completed_at: `2026-07-18T02:55:16.949812+00:00`
- quality: genesis RGB-D, no seed cut

| matrix | n | target |
| --- | ---: | ---: |
| physics-180 | 180 | 180 |
| formal-locked-3x6x100 | 1800 | 1800 |
| formal-learned-3x6x100 | 1800 | 1800 |
| ood-3x2x500 | 3000 | 3000 |

## by_policy (each matrix)

### physics-180
```json
{
  "purify-passive": {
    "n": 60,
    "mission": 60,
    "unsafe": 0,
    "repair_success": 0,
    "direct": 0,
    "detour": 60
  },
  "purify-active": {
    "n": 60,
    "mission": 60,
    "unsafe": 0,
    "repair_success": 10,
    "direct": 9,
    "detour": 51
  },
  "naive": {
    "n": 60,
    "mission": 25,
    "unsafe": 15,
    "repair_success": 0,
    "direct": 25,
    "detour": 0
  }
}
```

### formal-locked-3x6x100
```json
{
  "naive": {
    "n": 600,
    "mission": 250,
    "unsafe": 198,
    "repair_success": 0,
    "direct": 250,
    "detour": 0
  },
  "purify-passive": {
    "n": 600,
    "mission": 600,
    "unsafe": 0,
    "repair_success": 0,
    "direct": 0,
    "detour": 600
  },
  "purify-active": {
    "n": 600,
    "mission": 600,
    "unsafe": 0,
    "repair_success": 100,
    "direct": 94,
    "detour": 506
  }
}
```

### formal-learned-3x6x100
```json
{
  "purify-active-dagger": {
    "n": 600,
    "mission": 600,
    "unsafe": 0,
    "repair_success": 100,
    "direct": 100,
    "detour": 500
  },
  "purify-active-learned": {
    "n": 600,
    "mission": 600,
    "unsafe": 0,
    "repair_success": 100,
    "direct": 100,
    "detour": 500
  },
  "purify-random": {
    "n": 600,
    "mission": 470,
    "unsafe": 0,
    "repair_success": 68,
    "direct": 51,
    "detour": 549
  }
}
```

### ood-3x2x500
```json
{
  "purify-passive": {
    "n": 1000,
    "mission": 1000,
    "unsafe": 0,
    "repair_success": 0,
    "direct": 0,
    "detour": 1000
  },
  "naive": {
    "n": 1000,
    "mission": 250,
    "unsafe": 425,
    "repair_success": 0,
    "direct": 250,
    "detour": 0
  },
  "purify-active": {
    "n": 1000,
    "mission": 1000,
    "unsafe": 0,
    "repair_success": 250,
    "direct": 250,
    "detour": 750
  }
}
```

## v7 handoff
- Theme: Vision-Grounded Evidence Contracts
- Model proposes claims; Purify still authorizes
- Next agent: archive + V7_DESIGN scaffold
