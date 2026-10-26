"""Local tool: print LLM summaries to check the prompt; --update writes them to cards.

By default every dataset picked is summarized and the new summary is printed
next to the card's current one; nothing is written, and the dataset needs no
card. With --update each new summary is written into its card with its
docstring_hash, so a later generate_cards.py run keeps it. The model and the
prompt are in llm.py.

Usage:
    python scripts/local/run_llm_local.py --dataset beatles   # print one summary
    python scripts/local/run_llm_local.py                     # print every card's summary
    python scripts/local/run_llm_local.py --update            # write every card without one
    python scripts/local/run_llm_local.py --update --force    # rewrite every card

Notes:
    - With --update, cards that already have a summary are skipped unless --force.
"""

import argparse
import glob
import os
import sys
import time

import mirdata

# scripts/local/ -> scripts/, where the gallery code (card_utils, stats, llm) lives
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import card_utils
import llm


def main():
    parser = argparse.ArgumentParser(
        description="Summarize loader docstrings from mirdata with Qwen via llama.cpp."
    )
    parser.add_argument("--dataset", default=None, help="One dataset, e.g. 'beatles'")
    parser.add_argument(
        "--cards-dir", default="cards", help="Card directory (default: cards)"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write the new summaries into the cards (default: print only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --update: redo cards that already have a summary",
    )
    parser.add_argument(
        "--repo",
        default=llm.GGUF_REPO,
        help=f"Hugging Face GGUF repo (default {llm.GGUF_REPO})",
    )
    parser.add_argument(
        "--pattern",
        default=llm.GGUF_PATTERN,
        help=f"Which file in the repo (default {llm.GGUF_PATTERN})",
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
        path = card_utils.card_path(args.cards_dir, name)
        card = card_utils.read_card(path)  # None is fine when only printing
        if args.update and card is None:
            raise SystemExit(f"Card not found: {path}")
        if name not in known:
            print(f"[WARN] {name} is not a mirdata dataset, skipping")
            continue
        if args.update and card.get("summary") and not args.force:
            skipped += 1
            continue
        todo.append((name, path, card))

    if args.update:
        print(f"{len(todo)} dataset(s) to summarize, {skipped} already summarized")
    else:
        print(f"{len(todo)} dataset(s) to summarize (print only)")
    if not todo:
        return

    llm.configure(args.repo, args.pattern, args.model_path)
    llm.get_model()

    done = 0
    for name, path, card in todo:
        print(f"\n[{name}]")
        start = time.time()
        try:
            docstring = llm.loader_docstring(name)
            new = llm.summary(name, docstring) if docstring else None
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
        done += 1

        if not args.update:
            if card and card.get("summary"):
                print(f"  current:   {card['summary']}")
            continue

        card["summary"] = new
        card["docstring_hash"] = card_utils.docstring_hash(docstring)
        card_utils.write_card(path, card)

    if args.update:
        print(f"\nDone: wrote {done} summary(ies)")
    else:
        print(f"\nPrinted {done} summary(ies), nothing written (--update writes them)")


if __name__ == "__main__":
    main()
