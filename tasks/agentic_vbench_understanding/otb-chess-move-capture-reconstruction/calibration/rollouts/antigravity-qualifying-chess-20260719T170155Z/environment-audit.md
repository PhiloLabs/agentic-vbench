# Environment Audit

- The rollout used Antigravity CLI `1.1.1` with terminal sandboxing enabled and
  `BypassSandbox: false` on every command call.
- `PATH` selected a clean Python 3.12.7 virtual environment created without
  pip. Imports of NumPy, OpenCV, Pillow, python-chess, matplotlib, pandas,
  SciPy, and scikit-image were unavailable.
- The temporary permission profile denied URL reads, URL execution, and MCP.
  A pre-tool hook additionally denied web/browser/URL tools, package or network
  commands, sandbox bypass, outside-workspace file arguments, and explicit
  absolute command paths outside the workspace.
- The hook recorded 54 decisions: 53 allowed and 1 denied. The denied action was
  `which ffmpeg ffprobe python3 pip3 conda`; it was rejected because it named
  blocked package managers. No install or network operation ran.
- Transcript audit found zero web/URL/browser/MCP tool calls, zero HTTP(S)
  strings in tool arguments, zero sandbox bypasses, zero command working
  directories outside the rollout workspace, and zero file targets outside the
  rollout workspace.
- Two `manage_task` calls observed Antigravity's own asynchronous command tasks.
  Their system-generated logs lived under the same conversation's CLI brain;
  they did not expose external files, prior rollouts, ground truth, or network
  content.
- The fresh workspace contained only the processed video, empty `work/` and
  `output/` directories, and the run-local guard runtime. Ground truth and prior
  rollout artifacts were absent.
- The processed video SHA256 was
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`.
- The temporary global Antigravity settings and pre-tool hook were removed after
  the run, and the original settings file was restored byte-for-byte.
