"""Single entry point for reading the C<->Rust dataset.

Before this module the three pipelines each assumed a different shape of the
data - `c`/`rust`, `c_code`/`rust_code`, and a file called
`data/dataset_cleaned.jsonl` - so none of them ran against the released file.
Everything now goes through `load()`.

Schema v1.0:

    problem_id                  zero-padded id, "0001".."1886"
    origin                      "codenet" | "xcodeeval" | "common-algorithms"
    license                     SPDX expression governing this record
    problem_description         the upstream statement, verbatim
    problem_description_format  "html" | "text"
    c_code                      C implementation, entry point named solution()
    rust_code                   Rust implementation, entry point fn solution()
    difficulty                  "easy" | "medium" | "hard"
    split                       "train" | "val" | "test"

Records do not share a single licence - see DATA_LICENSES.md before
redistributing or using this data commercially.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(ROOT, "dataset.jsonl")

REQUIRED_FIELDS = (
    "problem_id",
    "origin",
    "license",
    "problem_description",
    "problem_description_format",
    "c_code",
    "rust_code",
    "difficulty",
    "split",
)


def load(path=None, split=None, origin=None, difficulty=None):
    """Read the dataset, optionally filtered.

    `split`, `origin` and `difficulty` each accept a string or a collection of
    strings. Passing split=None returns every pair.

    Note that filtering by origin also filters by licence - load(origin="codenet")
    is the subset that carries no commercial restriction.
    """
    path = path or DATASET
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Expected the dataset at dataset/dataset.jsonl; "
            f"run dataset/scripts/build_dataset_v1.py if you have a v0 file."
        )

    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            missing = [k for k in REQUIRED_FIELDS if k not in row]
            if missing:
                raise ValueError(
                    f"{path}:{lineno} is missing {missing}. This looks like the "
                    f"pre-v1.0 schema - run dataset/scripts/build_dataset_v1.py."
                )
            rows.append(row)

    rows = _filter(rows, "split", split)
    rows = _filter(rows, "origin", origin)
    rows = _filter(rows, "difficulty", difficulty)
    return rows


def load_pairs(**kwargs):
    """Return (c_texts, rust_texts, problem_ids) for the selected rows."""
    rows = load(**kwargs)
    return (
        [r["c_code"] for r in rows],
        [r["rust_code"] for r in rows],
        [r["problem_id"] for r in rows],
    )


def _filter(rows, field, wanted):
    if wanted is None:
        return rows
    if isinstance(wanted, str):
        wanted = {wanted}
    else:
        wanted = set(wanted)
    return [r for r in rows if r[field] in wanted]
