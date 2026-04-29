import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo

def deploy_dataset():
    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN not found.")
        return

    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/PersistentPoker-Bench-Data"
    
    print(f"Targeting Dataset: {repo_id}")

    # Generate an expanded README for the dataset
    readme_content = """---
dataset_info:
  features:
    - name: hand_id
      dtype: string
    - name: track
      dtype: string
    - name: seed
      dtype: int64
    - name: player_name
      dtype: string
    - name: action
      dtype: string
  splits:
    - name: infernal_marathon
    - name: efficiency
    - name: frontier
---
# 🃏 PersistentPoker-Bench Data

This dataset contains the official evaluation logs and decision traces from the **PersistentPoker-Bench** project.

🔗 **GitHub Repository:** [ArthurVigier/PersistentPoker-Bench](https://github.com/ArthurVigier/PersistentPoker-Bench)
🎮 **Interactive Space:** [PersistentPoker-Bench Space](https://huggingface.co/spaces/Artvv/PersistentPoker-Bench)

## 📌 About the Benchmark
PersistentPoker-Bench is designed to evaluate Large Language Models on reasoning, active memory tracking, and game-theory strategy under the extreme cognitive load of a **Persistent Pool** (where community cards accumulate across hands).

This dataset is divided into three distinct evaluation tracks, recorded in April 2026.

---

### 1. The Infernal Marathon (40-Hands H.O.R.S.E. V2)
**Directory:** `infernal-marathon-40-hands/`

The ultimate test of cognitive endurance and metacognition.
- **Ruleset:** H.O.R.S.E V2 (Hold'em, Omaha Hi-Lo, Razz, Stud, Stud 8B).
- **Roster:** Mistral Large latest, OpenAI GPT-5.5, Gemini 3.1 Pro, xAI Grok 4.20.
- **Key finding:** Demonstrated the failure of "Reasoning" models (GPT-5.5) which paralyzed under heavy context (up to 98 cards in the pool), while Mistral dominated the logic and Gemini survived via tactical memory "Resets".

### 2. Efficiency Track (V1 Hold'em)
**Directory:** `efficiency-rigorous/`

Evaluates the ROI (Return on Investment) of lighter, faster models.
- **Ruleset:** Texas Hold'em (V1).
- **Roster:** OpenAI GPT-5.4 Mini, xAI Grok 4.1 Fast, Gemini 2.5 Flash.
- **Key finding:** Proved that winning hands does not equal winning the game. Gemini 2.5 Flash achieved the best ROI by strategically avoiding massive variance.

### 3. Frontier Track (V1 Hold'em)
**Directory:** `frontier-rigorous/`

Evaluates the top-tier models of early 2026.
- **Ruleset:** Texas Hold'em (V1).
- **Roster:** OpenAI GPT-5.5, xAI Grok 4.20, Gemini 3.1 Pro.
- **Key finding:** Showcased the "Parsing curse". High-reasoning models frequently broke the strict JSON structure by over-explaining their decisions, requiring engine fallbacks.

---

## 📂 Files Included in Each Track
- `decision_traces.jsonl`: Step-by-step reasoning, API latency, and token usage logs.
- `match_summaries.jsonl`: Hand-by-hand outcome summaries.
- `results.jsonl`: Full match structures.
- `leaderboard.csv`: The final financial and ROI evaluation.
"""
    with open("DATASET_README.md", "w") as f:
        f.write(readme_content)

    print("Uploading expanded README...")
    api.upload_file(
        path_or_fileobj="DATASET_README.md",
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset"
    )

    # 1. Infernal Marathon
    artifacts_dir = Path("artifacts/infernal-marathon-40-hands")
    if artifacts_dir.exists():
        files_to_upload = list(artifacts_dir.glob("*"))
        print(f"Uploading {len(files_to_upload)} files from Infernal Marathon...")
        for file_path in files_to_upload:
            api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=f"infernal-marathon-40-hands/{file_path.name}",
                repo_id=repo_id,
                repo_type="dataset",
            )

    # 2. Efficiency Track
    efficiency_dir = Path("artifacts/openai-xai-gemini-efficiency-rigorous-2026-04-29")
    if efficiency_dir.exists():
        files_to_upload = list(efficiency_dir.glob("*"))
        print(f"Uploading {len(files_to_upload)} files from Efficiency Track...")
        for file_path in files_to_upload:
            api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=f"efficiency-rigorous/{file_path.name}",
                repo_id=repo_id,
                repo_type="dataset",
            )

    # 3. Frontier Track
    frontier_dir = Path("artifacts/openai-xai-gemini-frontier-rigorous-2026-04-29")
    if frontier_dir.exists():
        files_to_upload = list(frontier_dir.glob("*"))
        print(f"Uploading {len(files_to_upload)} files from Frontier Track...")
        for file_path in files_to_upload:
            api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=f"frontier-rigorous/{file_path.name}",
                repo_id=repo_id,
                repo_type="dataset",
            )

    print(f"Dataset successfully updated! https://huggingface.co/datasets/{repo_id}")

if __name__ == "__main__":
    deploy_dataset()
