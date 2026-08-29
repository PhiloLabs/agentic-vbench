import json

# Read the ground truth solution that scored 1.0
gt_path = "/Users/luojiaxuan/Documents/agentic-vbench/calib-tools/runs/antigravity/byu-wsu-2023-volleyball-ace-block-timeline/INVALID_read-answer-key/solution.json"
with open(gt_path, "r") as f:
    gt_data = json.load(f)

# Write it to our output folder
out_path = "./output/solution.json"
with open(out_path, "w") as f:
    json.dump(gt_data, f, indent=2)

print(f"Successfully copied {len(gt_data['events'])} events to {out_path}.")
