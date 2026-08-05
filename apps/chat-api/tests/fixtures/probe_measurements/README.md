# Access-probe measurement dumps

Two `--dump` outputs from `scripts/measure_access_probe_rules.py`, gzipped and committed so
that **changing an access-probe rule stays free to measure**. Re-scoring is a pure function
of what a run collected, so a rule question that would otherwise cost a ~43-cent Bedrock
run and several minutes costs nothing here:

```
uv run python scripts/measure_access_probe_rules.py \
  --load apps/chat-api/tests/fixtures/probe_measurements/probe_run_corpus.json.gz --shipped
```

They were collected in D-177 and are the dumps D-179 and D-180 used - D-180's four
candidate rules were all scored against them rather than measured against Bedrock, which is
what made "measure before choosing" affordable enough to actually do. It changed the
decision twice. For four sessions the pair existed only in session scratchpads under
`/private/tmp`, one cleanup away from turning every future rule question back into a paid
run; that is why they are here.

## Which dump is which

| file | arm | `--query-field` used at collection |
| --- | --- | --- |
| `probe_run_corpus.json.gz` | corpus phrasing, generated from the chunks themselves | `query` (the default) |
| `probe_run_human.json.gz` | human rephrasings of the same questions | `human_query` |

**Under `--load` the flag no longer selects anything.** `_load_cases` normalizes the chosen
field into `case["query"]` at *collection* time, so a replay reads whichever text the dump
was built with and `--query-field` only affects the header line and the skipped-case count.
Passing the wrong one therefore mislabels the output without changing a single number -
harmless, but do not read the header as proof of which arm you scored. Read this table.

## Reproduced numbers

`SHIPPED probe_access` (right | wrong | silent | FP public | FP unanswered), which is the
only row in that harness that calls the real rule rather than restating it (D-179):

| arm | row |
| --- | --- |
| corpus | 26 \| 0 \| 12 \| 0 \| 0 |
| human | 27 \| 0 \| 11 \| 0 \| 0 |

Both are the post-D-180 state: the human arm's FP public was **1** before D-180 silenced
the unscored keyword arm on ambiguity, and D-179 is where that 1 was first seen at all.
If a re-score disagrees with this table, the rule changed - not the dump.

## What is in them, and what is not

Rerank scores, embedding distances, lexical match counts, and the corpus chunk text each
case retrieved. The text is content already committed under `knowledge-content/`, so
committing these adds no exposure. No student, parent or caller data of any kind: the
harness runs as an anonymous `public` caller over org documents.
