"""The `summary` card field: a local LLM summarizes each loader's docstring.

The text comes straight from mirdata (`mirdata.datasets.<name>.__doc__`) and
is never stored in the card. The model is Qwen2.5-7B-Instruct as a 4-bit GGUF
file, run with llama.cpp on the CPU, so no GPU is needed.

`summary(name, docstring)` takes the text from `loader_docstring(name)`;
generate_cards.py calls it for each card whose docstring is new or changed.
The model is loaded on the first call and reused. To summarize existing
cards without rebuilding them, run scripts/local/run_llm_local.py.

Notes:
    - Requires llama-cpp-python and huggingface_hub (requirements-llm.txt).
    - The first run downloads the model (about 4.7 GB) into
      ~/.cache/huggingface. Later runs reuse it.
"""

import glob
import importlib
import os

import card_builder

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
    return card_builder.clean_text(doc) or None


def summary(name, docstring):
    """LLM summary of a loader docstring (from loader_docstring(name))."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Dataset name: {name}\n\nDataset description:\n{docstring}",
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
