# Real, read-only CPU evidence audit for the Look Twice V8 demo video.
#
# The builder invokes VHS with --output so this tape never writes a fixed media
# path into the repository. The prompt is sanitized before recording: no local
# username, home path, hostname, SSH endpoint or hardware identifier is shown.

Require python3
Require shasum
Require go

Set Shell "bash"
Set FontFamily "SF Mono"
Set FontSize 31
Set Width 1920
Set Height 1080
Set Padding 42
Set Framerate 30
Set Theme "TokyoNight"
Set WindowBar "Rings"
Set WindowBarSize 38
Set TypingSpeed 18ms

Hide
Type "export PS1='judge@look-twice $ '"
Enter
Type "clear"
Enter
Sleep 500ms
Show

Type "python3 scripts/verify_frozen_foundation.py --output /tmp/look-twice-v8-foundation-source-ready.json"
Enter
Sleep 5s

Type "shasum -a 256 release/v8-frozen/results/LOCKED_TEST_REPORT.json"
Enter
Sleep 4s

Type "cd purify_robotics && go test ./... && cd .."
Enter
Sleep 5s

Type "shasum -a 256 showcase/public/data/replays/*.json"
Enter
Sleep 5s
