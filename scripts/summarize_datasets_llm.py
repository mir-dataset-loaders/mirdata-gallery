"""Script to generate concise summaries for dataset yamls using a local LLM on HPC/GPU.

Usage:
    # 1. Using Hugging Face Transformers (Default, runs directly on GPU/CUDA):
    python utils/summarize_datasets_llm.py --model Qwen/Qwen2.5-7B-Instruct

    # 2. Re-summarize all (even existing):
    python utils/summarize_datasets_llm.py --force
"""

import argparse
from pathlib import Path
import yaml
import torch
from transformers import pipeline


def str_presenter(dumper, data):
    """Formats multiline strings with clean YAML block scalars."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)

SYSTEM_PROMPT = (
    "You are an expert in Music Information Retrieval (MIR). "
    "Your job is to summarize dataset descriptions into a single concise paragraph (2-3 sentences, maximum 60 words). "
    "Focus strictly on: 1) What audio content is included, 2) What annotations/ground truth are provided, "
    "and 3) The primary MIR task. Output ONLY the summary without any intro, markdown headers, or bullet points."
)


def init_local_pipe(model_name: str):
    """Initializes the Hugging Face text generation pipeline on GPU."""
    print(f"Loading local model '{model_name}' to GPU...")
    pipe = pipeline(
        "text-generation",
        model=model_name,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto",
    )
    return pipe


def summarize_docstring(pipe, name: str, docstring: str) -> str:
    """Generates a concise summary from a dataset docstring."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Dataset name: {name}\n\nDataset description:\n{docstring.strip()}",
        },
    ]

    prompt = pipe.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    outputs = pipe(
        prompt,
        max_new_tokens=150,
        do_sample=False,  # Deterministic output
        temperature=0.0,
        pad_token_id=pipe.tokenizer.eos_token_id,
    )

    generated_text = outputs[0]["generated_text"][len(prompt) :].strip()
    return generated_text


def main():
    parser = argparse.ArgumentParser(
        description="Summarize mirdata dataset docstrings with a local LLM"
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Name of a single dataset to summarize (e.g. 'beatles' or 'beatles.yaml')",
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Hugging Face model ID or path to local checkpoint",
    )
    parser.add_argument(
        "--yaml-dir",
        default="dataset_yamls",
        help="Directory containing dataset YAMLs",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-generate summaries even if they already exist",
    )
    args = parser.parse_args()

    yaml_dir = Path(args.yaml_dir)

    if args.dataset:
        dataset_name = args.dataset.replace(".yaml", "") ### beatles.yaml turns into beatles
        target_path = yaml_dir / f"{dataset_name}.yaml"
        if not target_path.exists():
            raise FileNotFoundError(f"Dataset YAML not found at: {target_path}")
        yaml_files = [target_path]
        print(f"Targeting single dataset: {dataset_name}")
    else:
        yaml_files = sorted(yaml_dir.glob("*.yaml"))


    # Load model once
    pipe = init_local_pipe(args.model)

    success_count = 0
    skipped_count = 0

    for yml_path in yaml_files:
        with open(yml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Skip if already summarized
        if "summary" in data and data["summary"] and not args.force:
            print(f"[SKIP] {yml_path.stem} already has a summary.")
            skipped_count += 1
            continue

        docstring = data.get("docstring")
        if not docstring or not docstring.strip():
            print(f"[WARN] {yml_path.stem} has no docstring. Skipping.")
            continue

        name = data.get("name", yml_path.stem)
        print(f"[SUMMARIZING] {name}...")

        try:
            summary = summarize_docstring(pipe, name, docstring)
            data["summary"] = summary

            with open(yml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)

            success_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to summarize {name}: {e}")

    print(
        f"\nFinished! Summarized: {success_count}, Skipped (cached): {skipped_count}"
    )


if __name__ == "__main__":
    main()
