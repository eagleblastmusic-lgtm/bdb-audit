"""Full-document Q1 schema contexts, independently judged, never authority.

Recipes retain exact full input hashes without copying large enclosing documents.
The frozen schema is the specification. The reference interpreter does not use
jsonschema or production validators to decide the expected result.
"""
import argparse
from collections import Counter
from copy import deepcopy
from itertools import product
import json
from pathlib import Path
from typing import Any, BinaryIO

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_model import LimitedCorpus, BASE
from tools.nf02_p0_q1 import Vectors, Unsatisfiable, merge, reference_a, reference_b
from tools.nf02_p0_reference import valid, sha

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    manifest = json.loads((ROOT / BASE / "CANDIDATE_MANIFEST.json").read_bytes())
    names = {r["file"] for group in ("normative", "machine") for r in manifest[group + "_files"]}
    names.add(BASE + "CANDIDATE_MANIFEST.json")
    return LimitedCorpus({n: (ROOT / n).read_bytes() for n in names})


def replaced(root, path, value, *, remove=False):
    result = deepcopy(root)
    if not path:
        return deepcopy(value)
    node = result
    for index, part in enumerate(path[:-1]):
        if isinstance(node, list):
            while len(node) <= part:
                node.append({} if isinstance(path[index + 1], str) else [])
        node = node[part]
    key = path[-1]
    if isinstance(node, list):
        while len(node) <= key:
            node.append(None)
    if remove:
        del node[key]
    else:
        node[key] = deepcopy(value)
    return result


def at(root, path):
    for part in path:
        root = root[part]
    return root


class Contexts:
    def __init__(self, output):
        self.output = output
        self.corpus = corpus()
        self.named = self.corpus.schemas.documents
        self.docs = {d["$id"]: d for d in self.named.values()}
        self.vectors = Vectors(self.named)
        self.counts: Counter[str] = Counter()
        self.obligations = []
        self.seen = set()
        self.bases = {}
        self.array_samples = {}
        self.stream: BinaryIO | None = None

    def sample_array(self, items, amount):
        key = reference_a(items)
        values = self.array_samples.setdefault(key, [])
        while len(values) < amount:
            values.append(self.vectors.sample(items, len(values) + 1))
        return values[:amount]

    def active(self, schema, value):
        s = self.vectors.resolve(schema)
        for union in ("oneOf", "anyOf"):
            choices = s.pop(union, None)
            if choices:
                matching = [b for b in choices if valid(b, value, self.docs)]
                if matching:
                    s = merge(s, self.active(matching[0], value))
        if "if" in s:
            choice = "then" if valid(s["if"], value, self.docs) else "else"
            s = merge({k: v for k, v in s.items() if k not in {"if", "then", "else"}}, s.get(choice, {}))
        return s

    def emit(self, name, base, path, value, label, *, remove=False, recipe=None):
        assert self.stream is not None
        full = replaced(base, path, value, remove=remove)
        raw = reference_a(full)
        digest = sha(raw)
        # Deduplicate bytes, retain all distinct full contexts (never node-only).
        key = name, digest
        if key in self.seen:
            return valid(self.named[name], full, self.docs)
        self.seen.add(key)
        try:
            assert raw == reference_b(full)
            cjson_domain = True
        except ValueError:
            cjson_domain = False  # Deliberate bound +/- 1 outside CJSON.
        expected = valid(self.named[name], full, self.docs)
        try:
            self.corpus.schemas.validate(name, full)
            actual = True
        except ValidationError:
            actual = False
        row = {"id": "CTX-%06d" % (len(self.seen)), "schema": name,
               "base_sha256": sha(reference_a(base)), "path": path,
               "mutation": label, "remove": remove,
               "input_exact_json_sha256": digest, "input_exact_json_bytes": len(raw), "in_cjson_domain": cjson_domain,
               "schema_sha256": sha(self.corpus.files[BASE + "schemas/" + name + ".schema.json"]),
               "expected_schema": expected, "actual_schema": actual}
        row.update({"replacement_recipe": recipe} if recipe else {"replacement": value})
        self.bases[row["base_sha256"]] = base
        self.stream.write(reference_a(row) + b"\n")
        self.counts[name] += 1
        if expected != actual:
            self.stream.flush()
            raise AssertionError(row)
        return expected

    def nodes(self, schema, value, path=()):
        yield path, schema, value
        s = self.active(schema, value)
        if isinstance(value, dict):
            for k, v in value.items():
                if k in s.get("properties", {}):
                    yield from self.nodes(s["properties"][k], v, (*path, k))
        elif isinstance(value, list) and "items" in s:
            # A single item witnesses every nested union; multiplicity and
            # uniqueness/bounds are exercised separately below.
            for index, item in enumerate(value[:1]):
                yield from self.nodes(s["items"], item, (*path, index))

    def root_contexts(self, name, doc):
        s = self.vectors.resolve(doc)
        contexts = []
        # Every root command branch includes its own fact/event counts.
        for seed in range(max(2, len(s.get("oneOf", [])))):
            try:
                contexts.append(self.vectors.sample(doc, seed))
            except Unsatisfiable:
                continue
        if name == "canonical/attempt__3":
            base = contexts[0]
            for prior, abort in product((False, True), repeat=2):
                v = deepcopy(base)
                for field, present in (("retry_of_attempt_ref", prior), ("abort_basis_ref", abort)):
                    branches = doc["properties"][field]["anyOf"]
                    branch = next(b for b in branches if (b.get("type") != "null") == present)
                    v[field] = self.vectors.sample(branch)
                contexts.append(v)
        if name == "external/INSTALLATION_RECORD__1":
            # Exact full 2 x 2 x 2 mode/RQ/mandate product including forbidden
            # combinations; expected is the independent conditional predicate.
            for mode, rq, mandate in product(("QUALIFICATION_ONLY", "PRODUCTION"), (None, "1" * 64), (None, "2" * 64)):
                v = deepcopy(contexts[0])
                v.update(mode=mode, runtime_qualification_sha256=rq, qualification_mandate_sha256=mandate)
                contexts.append(v)
        if name == "canonical/command_envelope__3":
            expanded = []
            for base in contexts:
                for mode, empty in product(("QUALIFICATION_ONLY", "PRODUCTION"), (False, True)):
                    v = deepcopy(base)
                    v["mode"] = mode
                    v["expected_parent"] = "EMPTY_HISTORY" if empty else self.vectors.sample(doc["properties"]["expected_parent"]["oneOf"][1])
                    expanded.append(v)
            contexts.extend(expanded)
        return list({sha(reference_a(v)): v for v in contexts}.values())

    def run(self):
        self.output.mkdir(parents=True, exist_ok=False)
        with (self.output / "CONTEXT_CASES.jsonl").open("xb") as stream:
            self.stream = stream
            for name, doc in sorted(self.named.items()):
                for base in self.root_contexts(name, doc):
                    root_valid = self.emit(name, base, (), base, "ROOT_BRANCH_PRODUCT")
                    if not root_valid:
                        continue
                    queue = [(base, ())]
                    visited = set()
                    while queue:
                        enclosing, prefix = queue.pop(0)
                        for path, schema, value in list(self.nodes(doc, enclosing)):
                            if prefix and path[:len(prefix)] != prefix:
                                continue
                            s = self.vectors.resolve(schema)
                            active = self.active(schema, value)
                            marker = (path, sha(reference_a(active)))
                            if marker in visited:
                                continue
                            visited.add(marker)
                            for union in ("oneOf", "anyOf"):
                                for index, branch in enumerate(s.get(union, [])):
                                    try:
                                        spec = merge({k: v for k, v in s.items() if k != union}, branch)
                                        selected = self.vectors.sample(spec, index)
                                    except Unsatisfiable:
                                        # The full field constraint excludes this target;
                                        # still execute a root negative for the raw branch.
                                        selected = self.vectors.sample(branch, index)
                                    ok = self.emit(name, enclosing, path, selected, union + "/" + str(index))
                                    self.obligations.append({"schema": name, "path": path, "branch": union + "/" + str(index), "full_context_admitted": ok})
                                    if ok:
                                        queue.append((replaced(enclosing, path, selected), path))
                            for index, selected in enumerate(active.get("enum", [])):
                                self.emit(name, enclosing, path, selected, "ENUM/" + str(index))
                            if isinstance(value, dict):
                                if active.get("additionalProperties") is False:
                                    self.emit(name, enclosing, path, {**value, "FORBIDDEN_EXTRA_FIELD": True}, "CLOSED_OBJECT")
                                for field in active.get("required", []):
                                    self.emit(name, enclosing, (*path, field), None, "REQUIRED/" + field, remove=True)
                            wrong_values: list[Any] = [None, True, 0, "WRONG_KIND_VERSION_SCHEMA", [], {}]
                            for wrong in wrong_values:
                                if not valid(schema, wrong, self.docs):
                                    self.emit(name, enclosing, path, wrong, "TYPE_CONST_PATTERN_NEGATIVE")
                            for keyword in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
                                if keyword not in active:
                                    continue
                                for offset in (-1, 0, 1):
                                    amount = active[keyword] + offset
                                    if amount < 0 and keyword not in {"minimum", "maximum"}:
                                        continue
                                    if keyword in {"minimum", "maximum"}:
                                        selected = amount
                                    elif "Length" in keyword:
                                        selected = "x" * amount
                                    else:
                                        selected = self.sample_array(active.get("items", {}), amount)
                                    recipe = ({"string_repeat": "x", "count": amount} if "Length" in keyword else
                                              {"array_samples": active.get("items", {}), "count": amount, "start_seed": 1} if "Items" in keyword else
                                              {"integer_decimal": str(amount)})
                                    self.emit(name, enclosing, path, selected, keyword + "/" + str(offset), recipe=recipe)
                            if isinstance(value, list) and "items" in active and active.get("maxItems", 1) > 0:
                                selected = self.vectors.sample(active["items"])
                                one = [selected] * max(1, active.get("minItems", 0))
                                ok = self.emit(name, enclosing, path, one, "NONEMPTY_NESTED_CONTEXT")
                                if ok:
                                    queue.append((replaced(enclosing, path, one), path))
                                self.emit(name, enclosing, path, [selected, selected], "DUPLICATE_ITEMS")
        (self.output / "CONTEXT_BASES.json").write_bytes(reference_a(self.bases) + b"\n")
        report = {"status": "PASS_RETAINED_FULL_DOCUMENT_CONTEXTS", "authority": "SCHEMA_ONLY_NO_AUTHORITY",
                  "case_count": sum(self.counts.values()), "per_schema": dict(self.counts),
                  "branch_obligations": self.obligations, "mismatches": [],
                  "expected_procedure": "tools/nf02_p0_reference.py:valid; no production/jsonschema backend",
                  "actual_procedure": "LimitedSchemas.validate on complete enclosing document",
                  "scope": "Every reachable nested branch/enum/required/closed/type/bound in each root operation context; exact conditional products for mode and paired retry refs. Independent fields do not imply all scalar values' Cartesian product.",
                  "inputs": [{"file": str(p.relative_to(ROOT)).replace('\\', '/'), "sha256": sha(p.read_bytes())} for p in [Path(__file__), ROOT / "tools/nf02_p0_reference.py", ROOT / "tools/nf02_p0_q1.py"]]}
        (self.output / "CONTEXT_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
        print("FULL_CONTEXTS_PASS", report["case_count"], "schemas", len(self.counts), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    Contexts(parser.parse_args().output).run()
