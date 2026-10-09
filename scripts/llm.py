"""The `summary` card field: a local LLM summarizes each loader's docstring.

The text comes straight from mirdata (`mirdata.datasets.<name>.__doc__`) and
is never stored in the card. The model is Qwen2.5-7B-Instruct as a 4-bit GGUF
file, run with llama.cpp on the CPU, so no GPU is needed.

`summary(ds)` takes an initialized dataset like the functions in
card_fields.py; generate_cards.py calls it for each card. The model is loaded
on the first call and reused.

Usage (standalone, to fill or redo summaries in existing cards):
    python scripts/llm.py --dataset beatles --force --dry-run
    python scripts/llm.py             # every card without a summary
    python scripts/llm.py --force     # redo every card

Notes:
    - Requires: pip install llama-cpp-python huggingface_hub
    - The first run downloads the model (about 4.7 GB) into
      ~/.cache/huggingface. Later runs reuse it.
    - Cards that already have a summary are skipped unless --force is given.
    - --dry-run prints the new summary next to the current one and writes nothing.
"""

import argparse
import glob
import importlib
import os
import textwrap
import time

import mirdata

import cards_io

SYSTEM_PROMPT = (
    "You are an expert in Music Information Retrieval (MIR). "
    "Your job is to summarize dataset descriptions into a single concise paragraph (2-3 sentences, maximum 60 words). "
    "Focus strictly on: 1) What audio content is included, 2) What annotations/ground truth are provided, "
    "and 3) The primary MIR task. Output ONLY the summary without any intro, markdown headers, or bullet points."
)

GGUF_REPO = "Qwen/Qwen2.5-7B-Instruct-GGUF"
GGUF_PATTERN = "*q4_k_m*.gguf"
MAX_NEW_TOKENS = 150
CONTEXT_TOKENS = 4096  # longest loader docstring is ~1500 tokens; this leaves room


# --- the card field -----------------------------------------------------------


def loader_docstring(name):
    """The module docstring of mirdata's loader for `name`, tidied, or None."""
    doc = importlib.import_module(f"mirdata.datasets.{name}").__doc__
    if not doc:
        return None
    lines = [line.rstrip() for line in doc.splitlines()]
    return textwrap.dedent("\n".join(lines)).strip() or None


def summary(ds):
    """LLM summary of the loader docstring, or None if the loader has none."""
    docstring = loader_docstring(ds.name)
    if not docstring:
        return None
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Dataset name: {ds.name}\n\nDataset description:\n{docstring}",
        },
    ]
    out = get_model().create_chat_completion(
        messages=messages, max_tokens=MAX_NEW_TOKENS, temperature=0.0
    )
    text = out["choices"][0]["message"]["content"]
    return " ".join(text.split()).strip().strip('"')  # one line, no stray quotes


# --- the model ----------------------------------------------------------------

_model = None
_model_args = (GGUF_REPO, GGUF_PATTERN, None)


def configure(repo=GGUF_REPO, pattern=GGUF_PATTERN, model_path=None):
    """Pick a different GGUF. Only needed before the first summary() call."""
    global _model, _model_args
    _model_args = (repo, pattern, model_path)
    _model = None


def get_model():
    """The loaded model, loading it on the first call."""
    global _model
    if _model is None:
        _model = load_model(*_model_args)
    return _model


def load_model(repo, pattern, model_path=None):
    """Download the GGUF (unless a local path is given) and load it.

    Qwen's official GGUF is split into shards; llama.cpp loads the rest
    automatically when given the first file.
    """
    from llama_cpp import Llama

    if model_path is None:
        from huggingface_hub import snapshot_download

        print(f"Fetching {pattern} from {repo} (cached after the first time)...")
        folder = snapshot_download(repo, allow_patterns=[pattern])
        files = sorted(glob.glob(os.path.join(folder, pattern)))
        if not files:
            raise SystemExit(f"No file matching {pattern!r} in {repo}")
        model_path = files[0]

    print(f"Loading {os.path.basename(model_path)}...")
    return Llama(
        model_path=model_path,
        n_ctx=CONTEXT_TOKENS,
        n_threads=os.cpu_count(),
        n_gpu_layers=-1,  # use a GPU if the build has one; ignored on CPU builds
        verbose=False,
    )


# --- standalone use -----------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Summarize loader docstrings from mirdata with Qwen via llama.cpp."
    )
    parser.add_argument("--dataset", default=None, help="One dataset, e.g. 'beatles'")
    parser.add_argument(
        "--cards-dir", default="cards", help="Card directory (default: cards)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Redo cards that already have a summary"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print summaries, write nothing"
    )
    parser.add_argument(
        "--repo",
        default=GGUF_REPO,
        help=f"Hugging Face GGUF repo (default {GGUF_REPO})",
    )
    parser.add_argument(
        "--pattern",
        default=GGUF_PATTERN,
        help=f"Which file in the repo (default {GGUF_PATTERN})",
    )
    parser.add_argument(
        "--model-path", default=None, help="Local .gguf file; skips the download"
    )
    args = parser.parse_args()

    if args.dataset:
        names = [args.dataset.removesuffix(".yaml")]
    else:
        paths = sorted(glob.glob(os.path.join(args.cards_dir, "*.yaml")))
        names = [os.path.basename(p).removesuffix(".yaml") for p in paths]

    known = set(mirdata.list_datasets())
    todo = []
    skipped = 0
    for name in names:
        path = cards_io.card_path(args.cards_dir, name)
        card = cards_io.read_card(path)
        if card is None:
            raise SystemExit(f"Card not found: {path}")
        if name not in known:
            print(f"[WARN] {name} is not a mirdata dataset, skipping")
            continue
        if card.get("summary") and not args.force:
            skipped += 1
            continue
        todo.append((name, path, card))

    print(f"{len(todo)} dataset(s) to summarize, {skipped} already summarized")
    if not todo:
        return

    configure(args.repo, args.pattern, args.model_path)
    get_model()

    written = 0
    for name, path, card in todo:
        print(f"\n[{name}]")
        start = time.time()
        try:
            new = summary(mirdata.initialize(name))
        except ModuleNotFoundError as e:
            print(f"  SKIP: loader needs an extra library ({e.name})")
            continue
        except Exception as e:  # keep going; the card keeps its old summary
            print(f"  ERROR: {e}")
            continue
        if new is None:
            print("  SKIP: loader has no docstring")
            continue
        print(f"  new ({time.time() - start:.0f}s): {new}")

        if args.dry_run:
            if card.get("summary"):
                print(f"  current:   {card['summary']}")
            continue

        card["summary"] = new
        cards_io.write_card(path, card)
        written += 1

    if args.dry_run:
        print(f"\nDry run: {len(todo)} summary(ies) generated, nothing written")
    else:
        print(f"\nDone: wrote {written} summary(ies)")


if __name__ == "__main__":
    main()
