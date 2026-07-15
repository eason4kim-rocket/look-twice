# AMD AI DevMaster Hackathon submission checklist

Verified on 2026-07-15 from the
[official Luma event page](https://luma.com/amd-4dhi) and the
[official submission repository](https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07).

## Deadline and eligibility

- Final deadline: **2026-08-06 23:59, Beijing/Singapore (UTC+8)**.
- Track: **Track 3 — Physical AI**.
- Team size: one to three people.
- AMD AI Developer Program membership is mandatory for prize eligibility.
- The Luma event requires registration approval.
- Review the linked Rules and Conditions document immediately before the final
  submission; it remains the governing document.

## Physical AI score alignment

| Criterion | Points | Look Twice evidence |
| --- | ---: | --- |
| Robot capability | 30 | Closed-loop inspect, deny, reinspect, detour and goal behavior |
| AMD Radeon / ROCm | 20 | W7900D Genesis, ROCm evidence corruption, MLP training and measured benchmark |
| Innovation | 20 | Temporal evidence gate, probabilistic belief and information-gain NBV |
| Real-world value | 20 | Preventing unsafe motion under occlusion, sensor failure and dynamic change |
| Upstream open source | 10 | No upstream contribution currently claimed; document this honestly |

## Required repository submission

- Fork `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`.
- Open a Pull Request containing the materials required by the official rules.
- PR title format: `Track 3, <Team name>, Look Twice`.
- Submit the project description, materials and PR in English.

These are external account actions and are intentionally left for the project
owner. The repository is ready to be linked from that PR.

## Ready artifacts

- [English submission draft](SUBMISSION_DRAFT.md)
- [Main README](../README.md)
- [V3 design and data-isolation diagram](V3_DESIGN.md)
- [500-episode core result](../results/2026-07-15_v3-formal/README.md)
- [Learned NBV result](../results/2026-07-15_v3-learned/README.md)
- [Annotated v3 demo](../assets/demo/v3/look-twice-v3-demo.mp4)
- [Raw/corrupted evidence and trajectory](../assets/demo/v3/README.md)

## Human actions before August 6

- [ ] Confirm Luma registration is approved.
- [ ] Confirm AMD AI Developer Program membership.
- [ ] Choose the public team name and list all members.
- [ ] Review the current Rules and Conditions document.
- [ ] Fork the official submission repository.
- [ ] Copy the English draft into the required submission structure.
- [ ] Upload or link the final 60–90 second edited video.
- [ ] Verify all links from a logged-out browser.
- [ ] Open the English PR before the deadline.
