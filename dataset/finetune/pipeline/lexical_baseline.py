"""
Lexical baseline: TF-IDF over shared identifiers, no model at all.

This exists because it beats zero-shot UniXcoder. On the test split it reaches
MRR 0.209 against 0.189, and 0.464 against 0.328 on the easy tier. Competitive
programmers reuse variable names across languages, so a C/Rust pair can often
be matched on name overlap without understanding either program.

Reporting it changes what the neural numbers mean. "A generic code model finds
this hard" is a weak claim when grep does better; "neither generic code
embeddings nor lexical matching solve this, and finetuning does" is the claim
the data actually supports, and this script is what licenses it.

Runs on CPU in seconds. Honours ANONYMIZE_IDENTIFIERS, which should collapse
it to near chance - that is the check that the ablation removes what it
claims to.

Usage:
    python lexical_baseline.py
    ANONYMIZE_IDENTIFIERS=1 python lexical_baseline.py
"""

import json
import math
import os
import re
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(ROOT, ".."))
from common.load import load  # noqa: E402
from common.runtime import anonymize_enabled, run_tag  # noqa: E402
from common.anonymize import anonymize_rows  # noqa: E402

from evaluate import evaluate_embeddings, print_results  # noqa: E402

RESULTS_DIR = os.path.join(ROOT, "outputs")

_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")

# Keywords carry no discriminative signal - every C program has `int` - and
# leaving them in would let two unrelated programs match on boilerplate.
_STOP = set("""
int long char float double void if else for while return struct sizeof const
static unsigned short signed break continue switch case default do goto typedef
enum union extern register volatile bool true false
fn let mut pub use impl match in as ref move type where trait crate self super
unsafe dyn loop mod i32 i64 u32 u64 usize f64 String Vec Option Some None
Result Ok Err
""".split())


def tokens(code):
    return [t for t in _IDENT.findall(code) if t not in _STOP]


def tfidf_vectors(docs):
    """Standard log-tf x idf, cosine-normalised later."""
    df = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
    out = []
    for d in docs:
        tf = Counter(d)
        out.append({t: (1 + math.log(c)) * idf.get(t, 1.0) for t, c in tf.items()})
    return out


def dense(vectors):
    """Project the sparse vectors onto the shared vocabulary.

    evaluate_embeddings wants dense rows; the vocabulary here is small enough
    (a few thousand terms over 187 documents) that this costs nothing, and it
    keeps this baseline scored by exactly the same code as the neural ones.
    """
    vocab = sorted({t for v in vectors for t in v})
    index = {t: i for i, t in enumerate(vocab)}
    m = np.zeros((len(vectors), len(vocab)), dtype=np.float32)
    for row, v in enumerate(vectors):
        for t, w in v.items():
            m[row, index[t]] = w
    return m


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    results_all = {}
    for split in ("val", "test"):
        rows = load(split=split)
        if anonymize_enabled():
            rows = anonymize_rows(rows)
            print("Identifier ablation: ON")

        c_docs = [tokens(r["c_code"]) for r in rows]
        r_docs = [tokens(r["rust_code"]) for r in rows]

        # fit idf over both languages together, so a term common to both is
        # correctly discounted
        vectors = tfidf_vectors(c_docs + r_docs)
        matrix = dense(vectors)
        n = len(rows)

        res = evaluate_embeddings(
            matrix[:n], matrix[n:], split_name=f"lexical_{split}",
            difficulties=[r["difficulty"] for r in rows],
            origins=[r["origin"] for r in rows])
        print_results(res)
        results_all[split] = res

    path = os.path.join(RESULTS_DIR, f"results_lexical{run_tag()}.json")
    with open(path, "w") as f:
        json.dump(results_all, f, indent=2)
    print(f"Saved {os.path.basename(path)}")


if __name__ == "__main__":
    main()
