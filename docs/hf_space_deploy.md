# Hugging Face Space Deployment

This document describes the exact deployment path for the current `PersistentPoker-Bench` web UI on Hugging Face Spaces.

## Recommended First Deployment

Use the current live web UI with:

- human seats
- OpenAI seats
- xAI seats
- DeepSeek seats

These are the easiest providers to run in the current Space without extra region routing setup.

## Repository Files Used by the Space

- Space entrypoint: `hf_space/app.py`
- Space dependencies: `requirements.txt`
- Space metadata: root `README.md`

The root `README.md` already includes the Hugging Face Spaces YAML header:

- `sdk: gradio`
- `sdk_version: 5.49.1`
- `app_file: hf_space/app.py`

## Create the Space

1. Create a new Space on Hugging Face.
2. Choose the **Gradio** SDK.
3. Push this repository to the Space repository.
4. Keep the default hardware for the first deployment unless you expect heavy multi-model traffic.

Official references:

- Hugging Face Spaces overview: <https://huggingface.co/docs/hub/en/spaces-overview>
- Hugging Face Gradio Spaces: <https://huggingface.co/docs/hub/spaces-sdks-gradio>
- Spaces config reference: <https://huggingface.co/docs/hub/main/spaces-config-reference>

## Space Secrets To Add

Add these secrets only for the providers you actually use.

### OpenAI

- `OPENAI_API_KEY`

Reference:

- LiteLLM basic usage for OpenAI: <https://docs.litellm.ai/>

### xAI

- `XAI_API_KEY`

References:

- xAI getting started: <https://docs.x.ai/docs/tutorial>
- LiteLLM basic usage for xAI: <https://docs.litellm.ai/>

### DeepSeek

- `DEEPSEEK_API_KEY`

References:

- DeepSeek first API call: <https://api-docs.deepseek.com/>
- DeepSeek OpenAI-compatible sample using `process.env.DEEPSEEK_API_KEY`: <https://api-docs.deepseek.com/api_samples/chat_nodejs/>

### Gemini

One of:

- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`

References:

- Google Gemini API key setup: <https://ai.google.dev/gemini-api/docs/api-key>

Important:

- for Gemini seats in this project, set `litellm_model` explicitly in the play config
- validate your LiteLLM route before publishing the Space publicly

### Qwen / DashScope

- `DASHSCOPE_API_KEY`

References:

- Alibaba OpenAI-compatible Qwen access: <https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope>

Important:

- Qwen seats in this project should set `litellm_model` explicitly
- for DashScope, also validate your `base_url` / region choice before publishing

## Recommended First Config

Use [configs/play_mixed.json](/Users/robertbadinter/Desktop/Poker-Bench/configs/play_mixed.json) for a first live mixed session.

Use [configs/frontier_live.json](/Users/robertbadinter/Desktop/Poker-Bench/configs/frontier_live.json) for a benchmark-style run.

## Local Dry Run Before Push

Install:

```bash
pip install -e '.[dev,llm,ui]'
```

Run the web UI locally:

```bash
persistentpoker-bench web --host 127.0.0.1 --port 7860
```

Run a mixed live session in terminal:

```bash
persistentpoker-bench play --config ./configs/play_mixed.json
```

## Space Runtime Notes

- Hugging Face Spaces supports environment secrets through the Space settings UI.
- Gradio Spaces install dependencies from `requirements.txt`.
- Free CPU Spaces may sleep when idle.

References:

- Spaces overview: <https://huggingface.co/docs/hub/en/spaces-overview>
- Spaces dependencies: <https://huggingface.co/docs/hub/spaces-dependencies>

## Practical Publishing Advice

- Start with only one paid provider seat plus one human seat.
- Keep `temperature=0.0` for benchmark consistency.
- Keep `max_tokens` bounded.
- Add only the secrets you need.
- Do not expose provider keys client-side.
- Keep replay JSON enabled for debugging first deployment issues.
