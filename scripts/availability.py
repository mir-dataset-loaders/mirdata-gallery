"""The `availability` card field: can a dataset's audio and annotations be downloaded?

The local LLM from llm.py answers one narrow question: do the download links
(REMOTES) hold the audio, and the annotations? Every REMOTES link is public, so
a part they hold is public. The parts they don't hold are labelled from words
in the download note (DOWNLOAD_INFO). Each part gets one of LABELS.
"""

import hashlib

import card_builder
import llm
import stats

LABELS = ("public", "on request", "not available", "unknown")

LINKS_PROMPT = (
    "You are an expert in Music Information Retrieval (MIR) datasets. "
    "You get a dataset's download links (one 'key: filename' line each) and its "
    "description. Decide whether the files behind these links hold the dataset's "
    "audio, and whether they hold its annotations (labels, metadata or scores). "
    "Answer 'none' when the dataset has no such part at all (for example, a dataset "
    "of scores or features has no audio). Answer in exactly three lines:\n"
    "reason: <one sentence>\n"
    "audio: <yes|no|none>\n"
    "annotations: <yes|no|none>"
)

# Words in the download note, checked in this order. "request" comes first:
# "not available for free download, but upon request" is on request.
NOTE_KEYWORDS = (
    ("request", "on request"),
    ("not available", "not available"),
    ("purchase", "not available"),
    ("buy", "not available"),
)

MAX_NEW_TOKENS = 120


def loader_texts(ds):
    """What the loader says about getting the data.

    Args:
        ds (mirdata.core.Dataset): the initialized dataset

    Returns:
        dict: "links" (one "key: filename" line per REMOTES link), "note"
            (DOWNLOAD_INFO) and "description" (the docstring); "" when missing

    """
    remotes = ds.remotes or {}
    return {
        "links": "\n".join(
            f"{key}: {remote.filename}" for key, remote in remotes.items()
        ),
        "note": card_builder.clean_text(ds._download_info) or "",
        "description": llm.loader_docstring(ds.name) or "",
    }


def availability_hash(texts):
    """Hex SHA-256 of what availability() reads.

    Args:
        texts (dict): from loader_texts()

    Returns:
        str: the hash

    """
    text = "\n\n".join(texts[key] for key in ("links", "note", "description"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_answer(answer, allowed):
    """Read the LLM's "part: value" lines.

    Args:
        answer (str): the LLM's reply
        allowed (tuple): the values a part may take

    Returns:
        dict: {part: value} for every part in stats.PARTS; a missing part or a
            value not in allowed is "unknown"

    """
    found = {}
    for line in answer.lower().splitlines():
        part, _, value = line.partition(":")
        part = part.strip(" *-`")
        value = value.strip(" *.`'\"")
        if part in stats.PARTS and part not in found:
            found[part] = value if value in allowed else "unknown"
    return {part: found.get(part, "unknown") for part in stats.PARTS}


def note_label(note):
    """The label the download note gives the parts the download links don't hold.

    Args:
        note (str): the loader's DOWNLOAD_INFO ("" when it has none)

    Returns:
        str: the label of the first NOTE_KEYWORDS word found in the note, or
            "unknown"

    """
    text = note.lower()
    for word, label in NOTE_KEYWORDS:
        if word in text:
            return label
    return "unknown"


def availability(name, texts):
    """Whether the dataset's audio and annotations can be downloaded.

    With download links, the LLM says which parts they hold (public) and which
    parts the dataset does not have (not available). Every other part, and
    every part of a dataset with no links, gets the note's label (note_label).

    Args:
        name (str): the dataset name
        texts (dict): from loader_texts()

    Returns:
        dict: {"audio": label, "annotations": label}, each one of LABELS

    """
    from_note = note_label(texts["note"])
    if not texts["links"]:
        return {part: from_note for part in stats.PARTS}
    question = (
        f"Dataset name: {name}\n\nDownload links:\n{texts['links']}\n\n"
        f"Description:\n{texts['description'] or 'none'}"
    )
    messages = [
        {"role": "system", "content": LINKS_PROMPT},
        {"role": "user", "content": question},
    ]
    out = llm.get_model().create_chat_completion(
        messages=messages, max_tokens=MAX_NEW_TOKENS, temperature=0.0
    )
    held = parse_answer(out["choices"][0]["message"]["content"], ("yes", "no", "none"))
    from_links = {"yes": "public", "none": "not available"}
    return {part: from_links.get(held[part], from_note) for part in stats.PARTS}
