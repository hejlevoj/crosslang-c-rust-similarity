"""Identifier anonymisation, for the ablation that asks what the models match on.

A TF-IDF baseline over shared identifiers reaches MRR 0.209 on the test split,
which beats zero-shot UniXcoder at 0.189. Competitive programmers reuse
variable names across languages, so a C/Rust pair can be matched by name
overlap alone without any understanding of the code. That leaves an obvious
question about every number in this repository: how much of it is structure,
and how much is `n`, `ans` and `dp` appearing on both sides?

`anonymize()` answers it by renaming user identifiers to positional names
(v1, v2, ...) independently on each side, destroying the cross-language name
correspondence while leaving control flow, types and library calls intact.

This is a deliberately approximate transformation. Telling a user variable from
a library symbol without parsing is not possible in general, so anything in
KEEP below is preserved and everything else is renamed. Over- or under-renaming
a few symbols does not affect the conclusion as long as the same rule is
applied to both languages, which it is.
"""

import re

_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")

# One pass over the source, matching whatever comes first. String and char
# literals and #include targets are consumed whole and returned untouched:
# renaming inside them would rewrite "%d" to "%v3" and change what the program
# does, which is noise rather than the signal this ablation removes. Comments
# are already stripped by the normalisation pipeline.
_SCAN = re.compile(
    r'''(?P<inc>\#\s*include\s*<[^>\n]*>)'''
    r'''|(?P<raw>r\#*"(?:[^"]|"(?!\#))*"\#*)'''
    r'''|(?P<str>"(?:\\.|[^"\\\n])*")'''
    r'''|(?P<chr>'(?:\\.|[^'\\\n])')'''
    r'''|(?P<id>[A-Za-z_][A-Za-z_0-9]*)''',
    re.VERBOSE,
)

# Language keywords. Renaming these would not compile and would destroy the
# structure the ablation is trying to preserve.
_C_KEYWORDS = """
auto break case char const continue default do double else enum extern float
for goto if inline int long register restrict return short signed sizeof static
struct switch typedef union unsigned void volatile while
_Bool _Complex _Imaginary bool true false NULL
""".split()

_RUST_KEYWORDS = """
as async await break const continue crate dyn else enum extern false fn for if
impl in let loop match mod move mut pub ref return self Self static struct super
trait true type union unsafe use where while
i8 i16 i32 i64 i128 isize u8 u16 u32 u64 u128 usize f32 f64 bool char str
String Vec Option Some None Result Ok Err Box HashMap HashSet BTreeMap VecDeque
""".split()

# Library surface both languages lean on. Renaming printf or push_str would
# turn the code into something no model could read, which is not the question
# being asked.
_C_STDLIB = """
printf scanf puts putchar getchar gets fgets sscanf sprintf snprintf fprintf
malloc calloc realloc free memset memcpy memmove strlen strcpy strncpy strcmp
strncmp strcat strchr strstr strtok atoi atof atol abs labs qsort bsearch
pow sqrt fabs floor ceil round log log2 log10 exp sin cos tan min max
stdin stdout stderr EOF INT_MAX INT_MIN LONG_MAX LONG_MIN RAND_MAX
include define ifndef endif main
""".split()

_RUST_STDLIB = """
std io stdin stdout stderr BufRead BufReader BufWriter Read Write Lines
read_line read_to_string write writeln print println eprint eprintln format
parse trim split split_whitespace splitn lines chars bytes collect iter
into_iter iter_mut map filter fold rev enumerate zip take skip sum product
count min max min_by max_by min_by_key max_by_key sort sort_by sort_unstable
sort_by_key push pop insert remove get get_mut contains contains_key len
is_empty clear extend append truncate resize with_capacity new default clone
to_string to_owned as_str as_bytes unwrap unwrap_or unwrap_or_else expect
abs pow sqrt powi powf floor ceil round signum wrapping_add saturating_sub
checked_add from into try_into cmp partial_cmp Ordering Less Greater Equal
entry or_insert or_default and_then ok_or matches swap replace mem
lock next next_back peek last first nth position find any all flat_map
flatten chunks windows join concat repeat starts_with ends_with to_vec
to_uppercase to_lowercase is_empty saturating_add checked_sub abs_diff
binary_search dedup retain drain splice reverse fill copy_from_slice
borrow borrow_mut as_ref as_mut deref cloned copied unwrap_err is_some
is_none is_ok is_err take_while skip_while step_by scan peekable
usize_MAX MAX MIN INFINITY NEG_INFINITY EPSILON
main solution
""".split()

KEEP = frozenset(_C_KEYWORDS + _RUST_KEYWORDS + _C_STDLIB + _RUST_STDLIB)


def anonymize(code, prefix="v"):
    """Rename user identifiers to positional names, in order of first use.

    The prefix matters. Renaming both sides of a pair with the same prefix
    does not remove the name signal, it manufactures one: the first variable
    becomes v1 in the C code and v1 in the Rust code, and identifier overlap
    goes *up*. Measured on this dataset, a shared prefix lifts the mean
    C/Rust identifier Jaccard from 0.133 to 0.226. Use disjoint prefixes per
    language, as `anonymize_rows` does.
    """
    # A generated name that collides with a real identifier would merge two
    # distinct variables, so lengthen the prefix until it cannot happen.
    existing = set(_IDENT.findall(code))
    while any(n.startswith(prefix) and n[len(prefix):].isdigit() for n in existing):
        prefix += "_"

    mapping = {}

    def rename(match):
        name = match.group("id")
        if name is None:            # a literal or an #include: leave it alone
            return match.group(0)
        if name in KEEP:
            return name
        if name not in mapping:
            mapping[name] = f"{prefix}{len(mapping) + 1}"
        return mapping[name]

    return _SCAN.sub(rename, code)


C_PREFIX = "cv"
RUST_PREFIX = "rv"


def anonymize_rows(rows):
    """Return copies of `rows` with c_code and rust_code anonymised.

    The two languages get disjoint name spaces (cv1... and rv1...), so no user
    identifier can match across a pair. What overlap survives is keywords,
    types and library calls - the structural signal the ablation is meant to
    leave intact.
    """
    out = []
    for r in rows:
        r = dict(r)
        r["c_code"] = anonymize(r["c_code"], C_PREFIX)
        r["rust_code"] = anonymize(r["rust_code"], RUST_PREFIX)
        out.append(r)
    return out
