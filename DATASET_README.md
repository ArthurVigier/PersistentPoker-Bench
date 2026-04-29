---
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
