# Configuration report-inventory continuation — 18 September 2026

**SOURCE-ONLY / DORMANT / NOT_WORKFLOW_WIRED. Apps are not in Releases.**
This follows the [closed producer-parent increment](hosted-bootstrap-producer-parent-2026-09-18.md)
at `ce4e1cbf0fbfc4d142bc14ef73b275dcb4aa7046`, not a replay of accepted locks,
preview or fixture work. The containing commit and remote readback belong in
[#437](https://github.com/p2pKit/P2pKit/issues/437), with #424 only as a shared
ordinary-CI prerequisite. No production/native/cache/collector execution occurs.

## Scope and API

The new [inventory helper](../../scripts/hosted_cache_bootstrap_collection.py)
accepts six immutable supplied originals and the separately supplied original
exit. It calls the unchanged configuration producer observer and validates the
canonical report manifest, never a live file. Consistency of supplied records
cannot authenticate a producer, original closed owner, file bytes or next call.

All six inputs and returned compact inventory must be exact nonempty bytes,
at most4MiB each. This outer envelope raises `CollectionError`, including for
oversized producer inputs; deeper producer consistency/identity/exit failures
propagate unchanged `ProducerError`. Inventory/descriptor errors are finite
`BOOTSTRAP_COLLECTION_*` codes, not echoed private paths or payloads.

- Manifest is UTF-8 with exactly schema1, records and the canonical limitation.
  Reject duplicate/nonfinite JSON, BOM/NUL and UTF16/32 reinterpretation.
  Original pretty start/receipt/manifest hashes and byte counts are retained;
  reserializing equivalent JSON cannot validate an earlier inventory.
- Rows have exact classification-dependent fields. Changed rows require
  `retained == "reports/" + source`; unchanged rows forbid a retained payload.
  The entire ordered receipt roster agrees by typed canonical JSON, not Python's
  `True == 1`. Exact integer sizes, lowercase SHA256 and SHA256(empty) for zero
  bytes are checked;512MiB aggregate includes unchanged rows and equal hashes
  do not deduplicate allocations.
- Only fixed-help build/report-root families are accepted, not external/-p roots.
  Sorted unique source names and a bounded trie reject whole-name/ancestor case
  aliases and file/directory-prefix conflicts. The deliberate portable ASCII
  grammar supports internal spaces/$ but rejects unsafe components and Windows
  device names, including device stems with spaces before extensions.
- Component255/source4096/report-directory-depth256 and a20,000-entry cap on the
  minimum declared report-tree count are metadata bounds, **not native path admission**. Represented report
  roots/directories count; source-root ancestors and unobserved empty trees do not.
  The declared minimum is not an actual archive or retained-destination count.
- Four canonical logs remain explicit64MiB-each `NOT_READ` requirements, without
  invented size/hash/existence. Payload ceiling excludes metadata and can reach
  768MiB, more than Snapshot576MiB. This is not streaming/custody or timing proof.

Output keeps collection `NOT_PERFORMED`, no-loader/native retirement unobserved,
input provenance `SUPPLIED_RECORDS_ONLY`, dependency population `NOT_ATTESTED`,
budget `NOT_ADMITTED`, tests `NOT_PERFORMED`, and successor/export/save authority
false. Changed bytes do not prove test execution; empty/unchanged reports cannot
prove nonexecution or reconstruct deleted or same-byte-rewritten outputs. Failed
producers still need separate original failure custody, not disposal or promotion.

## Exact source and executed offline evidence

Implementation approval: **APPROVE_EXACT_CONFIGURATION_INVENTORY_R3_SOURCE_ONLY**.
The independent report `IMPLEMENTATION_REVIEW_R3.md` has SHA256
`f4b694d4f7e41742396547b6827c3c9403da618f5351c761a263c9de56cc8fcd`;
its verdict seal has SHA256
`76e6515b37cb2609d8681ac3487361c180e7b983821ed740366b521d5fcad839`.
Complete-patch approval is separately bound in the issue mapping, never formal
GitHub different-account PR approval.

| Binding | SHA-256 |
| --- | --- |
| Inventory helper | `02e253894dc91200d3bfbb3ea3bb3cba7edfda643a3d7677759d8ce42ad2288c` |
| Author38 control file | `18be2180f4db8e7ed3e4269cad584bd6517d73f24f2fa2c610e11fa219a0747b` |
| Implementation-only patch | `6e9d736eed9bd8ac7667f29d1d0d6b5e9049ff569b7d19c85fd7d007c1eb7b74` |
| Author original-result readback | `4383184c538657ac79540c03709a0b9bff82fe6c2b8683dec26a4fd51fe299ba` |
| Independent prospective33 freeze | `149b30665d7fc70914c94898b77ddcc6cadc5f6f00932e171b0fe5ef91b18635` |

Implementation-only tree `70b054bad1ef4f5ce98d7052622470abc3dee248`.
The [author class](../../scripts/tests/hosted-cache-bootstrap-collection-test.py)
contains38 own methods, with **38 distinct method passes across two runs**, not
a successful whole38 aggregate. It composes only existing modeled producer fixture
setup and pure JSON/argv formatters, with no inherited historical test methods,
canonical main/execute, native or report-file collection.

| Author invocation | Original result | unittest / outer seconds |
| --- | --- | --- |
| R1 preimage device-stem1 | FAILED: one method, eight failed subcases,0errors | .017 / .315214 |
| R2 all38 | FAILED:37passed,1failed,0errors |2.101 /2.421719|
| R3 corrected malformed1 |1/1 PASS|.005 /.314797|

The preimage looked up an untrimmed device stem before the first dot. The only
implementation repair trims ASCII spaces for that reserved-name lookup, never
normalizing returned labels or changing shared native file helpers. Its desired
assertions are unchanged and passed in R2.

The one R2 failure was a fixture mistake:1200 balanced arrays were valid JSON,
missing a required field; an assumed parser recursion refusal was not established.
R3 deliberately leaves one bracket unmatched at the same depth and keeps the exact
`MANIFEST_JSON` expectation. Only that fixture method changed; all other37 methods,
helper bytes and fixture setup are identical. The successful37 were not rerun.

Actual UID/EUID65534, Python3.12.3 `-I -B -S`, immutable root-owned source copy;
45-second wall +5-second kill,60-second recorder, CPU30/768MiB/2MiB-output/FD64.
Audit/patch guards prohibit subprocess/network/native factories, thread launch and
filesystem writes. The pure I/O-negative also denies file/stat/directory/clock
suppliers. Large sizes are declarations and only a few MiB of JSON are allocated.
All1,432 copied source/content/metadata and same-process interpreter bindings
remained unchanged; raw stdout/stderr/exits/failures were retained and read back.

The independent33 were authored and frozen before helper/author-test inspection.
After those methods were authored, but before their freeze, the author disclosed
device-stem spacing; the reviewer did not add that case or claim its independent
origination. Full source and original author
results were independently read/hashed, including all1,432 source files in each
original snapshot; this was passive review, not a replay of those tests.

| Independent invocation | Original result | unittest seconds |
| --- | --- | --- |
| Original frozen33 on exact R3 | FAILED:32passed; one errored method, two error entries;0assertion failures |3.675|
| Strict corrected ONLY26 on unchanged R3 |1/1 PASS,0failures/errors|.138|

The original method26 incorrectly expected `ProducerError` for an oversized
upstream raw input. The source refused it with the all-six outer envelope's exact
`CollectionError("BOOTSTRAP_COLLECTION_METADATA_BYTES")`; no invalid record was
admitted. A subsequent `.exception` lookup outside `subTest` added an
`AttributeError`, so the remaining oversized vectors and exact-limit positives
were not reached in that original method. Deeper producer semantics retain
`ProducerError`; the separate independent method29 passed unchanged.

The separately frozen correction changed only method26: all five oversized
upstream vectors now require exact `CollectionError` and the exact metadata
code, plus the same two exact-limit start/receipt positives. Post-catch checks
stay inside `subTest`. All seven vectors in that one method passed. This is an
explicit post-source-exposure API/reviewer-fixture correction, not a weakened
limit, broad exception union, new source repair or untouched prospective33 pass.
The original FAILED33 stays failed:32 passing methods plus corrected1, never a
successful whole33 aggregate or additional product/runtime cases.

Actual UID/EUID65534, Python3.12.3 `-I -S -B`, separate root-owned0440/0550
source copy readable by group65534, CPU45/768MiB/2MiB-output/FD128 and wall90
bounded both executions.
Native/process/network/file-write suppliers were forbidden. An earlier passive
preparation refusal required zero writable mode bits from the lead's0644 copy:
zero tests ran, then a separate byte-identical read-only copy was created. That
refusal remains preserved rather than relabeled as a test result.

| Independent evidence binding | SHA-256 |
| --- | --- |
| Original frozen33 control file | `15969180b0156e4e3929de7c91782e16081dd617b0446d16431811defac1f607` |
| Original FAILED33 result | `66f64120ab353fd2cd7a5dfb242a5e259d773a194110b36835fa1b1214c1c677` |
| Corrected ONLY26 freeze | `d64105b439ea16946fc1a913c13a83971a3af593dfb9ac781c90c02f8f0fe638` |
| Corrected ONLY26 result | `4d87b91d3eb7153828042a11a50c1fec4c7d6849464f40d572c4e96062840996` |
| Passive author-original readback | `633c9eeacd19d14df2805c4a5feee14fe19bcf423028e8277e87284ea799111b` |

Private packets `20260918-bootstrap-collection-savpndbq` and
`inventory-implementation-r3-readonly.ppjf9wij` and
`inventory-boundary-correction-r2.IeNCt2d3` retain originals. Hashes are
navigation, not signatures or substitutes for missing originals. No private
original, cache, key, credential or old binary is published with this record.

## Remaining integration and acceptance

Next is the separate actually claimed original-call collection parent and bounded
file copying. It must follow the actual closed producer, carry its final RAW/LOCAL
high-waters and original file/directory bindings, and use NEW handles under its own
original collection phase. Never reopen that producer's owner/reader/READ30 or write
inside its still-empty retained directory before return. An ordinary collector or
loader-uninstall cannot be repurposed as configuration evidence. The existing
native file readers have narrower grammar/member/depth limits than this parser;
do not silently widen them or equate grammar acceptance with file admission.

Honest no-loader observation, positive dependency export/freeze/save-set checks,
provider save/probe, encrypted custody and separate seal/delivery remain unfinished.
No bootstrap workflow exists and no production caller invokes `cache.export_snapshot`
or `cache.save_set`. Ordinary suppliers/composition expectations, exact selectors,
credential boundaries and both activation HOLDs are unchanged. Configuration help
cannot satisfy ABI, simulator, Test-event/XML/export or ordinary FULL acceptance.

Fresh complete paginated metadata **2026-09-18 23:33:34 UTC**,45 verified requests:
78 open issues, seven dependency PRs, no campaign PR, zero queried active Actions,
two RC Releases with zero assets. Only the ce4e1cbf comments were new in the scoped
#437/#424/#457/#143/#144 conversations. Required checks remain `complete-gate`,
`review`, `scan / osv-scan`, `osv-scanner`; the owner's formal different-account
approval is still required despite configured review count0.

The absent `.github/test-evidence-recipient.json` still requires a named routine
custodian, exact public key, finite14-day policy, legitimate trusted-original-base
bootstrap and formal approval. Candidate source cannot authorize itself. Genuine
native/provider/resolver/custody/scheduling/delivery qualification, required checks,
formal PR approval and normal main merge/preservation precede development Releases.
5400 remains UNADMITTED/UNMEASURED; NativeFile900/Snapshot576MiB unchanged.

Preview35070982169 was not rebuilt/redownloaded: APK/MSI/ARM64-DMG/DEB remain Actions
artifacts expiring September30, not Releases. #424 writer35066719641/1 and six
original exports remain accepted in their exact scope. #372's20 Kotlin tests stay
uncompiled/unexecuted. Refreshed policy/advisory remains EXCEPTED_NOT_FIXED,
Kotlin2.4.10 affected, expiry2026-10-31; no scan/remediation/extension. Protected
instructions, immutable RC history/compatibility, unrelated work and proposals
#95/#97/#106/#107/#108/#452/#453 stay intact. No phones, production/Maven/Store
publication, PR/merge, release/tag/settings change or issue closure here.
Historical206/234 repair-approved,207/234 resolved; audit/release **NOT_READY**.

## Exact executed author selections

The original private recorder is bound by SHA256
`1e53aac4b2244870654416e9c4b72ffc49076663ec930f9423ed0173a0a3db22`;
its observer SHA256 is `1355ead776c13407bdc2d6b8561f6e3eab6db552951087e2f226c25166fd83b3`.
It loads only the explicitly listed methods from the immutable source copy under
the ordinary-UID bounds above, never the test file main or prior suites. These
are historical argument suffixes to `python3 -I -B -S run-controls.py`, not an
instruction to repeat successful checks. Original argv/env/output remain private.

### R1 intended preimage

```text
implementation-r1 author-r1-preimage1 \
  InventoryModels.test_reserved_device_stems_with_spaces_before_extensions_are_refused
```

Original result SHA256:
`140be09bf60e8d8a9d37dce59273492bfe8dd7625375712f9ac18344c53134f7`.

### R2 failed aggregate (37 passing methods retained)

```text
implementation-r2 author-r2-all38 \
  InventoryModels.test_empty_reports_still_require_four_unread_logs_and_no_authority \
  InventoryModels.test_mixed_inventory_preserves_classification_without_following_unchanged_sources \
  InventoryModels.test_fixed_help_output_root_families_and_portable_report_names \
  InventoryModels.test_six_modeled_cohorts_remain_separate_from_any_native_acceptance \
  InventoryModels.test_exact_pretty_original_hashes_and_byte_counts_are_not_compact_rewrites \
  InventoryModels.test_equivalent_manifest_reserialization_cannot_validate_old_inventory \
  InventoryModels.test_every_input_requires_exact_bounded_nonempty_bytes \
  InventoryModels.test_manifest_metadata_exact_limit_and_one_byte_over \
  InventoryModels.test_manifest_top_level_shape_schema_and_limitation_are_closed \
  InventoryModels.test_duplicate_fields_trailing_json_and_nonfinite_manifest_are_refused \
  InventoryModels.test_manifest_utf16_utf32_bom_and_invalid_utf8_are_not_reinterpreted \
  InventoryModels.test_report_roster_requires_list_with_twenty_thousand_upper_bound \
  InventoryModels.test_report_rows_have_exact_classification_dependent_fields \
  InventoryModels.test_report_sizes_are_exact_nonnegative_integers_bounded_per_file \
  InventoryModels.test_report_hashes_are_exact_lowercase_sha256_and_empty_digest_is_consistent \
  InventoryModels.test_aggregate_includes_unchanged_reports_at_original_512mib_limit \
  InventoryModels.test_declared_maximum_payload_exceeds_snapshot_without_becoming_observed_bytes \
  InventoryModels.test_source_order_and_exact_duplicates_are_refused \
  InventoryModels.test_case_aliases_in_files_and_ancestors_are_refused \
  InventoryModels.test_file_directory_prefix_conflicts_are_refused \
  InventoryModels.test_retained_paths_cannot_escape_or_relabel_original_source \
  InventoryModels.test_absolute_traversal_backslash_empty_and_drive_components_are_refused \
  InventoryModels.test_windows_device_names_punctuation_and_trailing_dots_spaces_are_refused \
  InventoryModels.test_reserved_device_stems_with_spaces_before_extensions_are_refused \
  InventoryModels.test_external_unknown_nested_and_nonreport_roots_are_refused \
  InventoryModels.test_component_source_and_report_depth_boundaries \
  InventoryModels.test_minimum_archive_members_count_roots_and_shared_directories_not_source_ancestors \
  InventoryModels.test_minimum_member_limit_is_inclusive_and_counts_the_report_root \
  InventoryModels.test_manifest_receipt_rows_match_typed_values_not_python_boolean_equality \
  InventoryModels.test_manifest_receipt_list_order_missing_and_extra_rows_are_refused \
  InventoryModels.test_original_request_and_source_binding_are_checked_before_inventory \
  InventoryModels.test_supplied_exit_failure_and_reported_stop_failure_cannot_be_promoted \
  InventoryModels.test_inventory_validation_rederives_exact_bytes_and_refuses_authority_upgrade \
  InventoryModels.test_inventory_validation_requires_exact_nonempty_bounded_bytes \
  InventoryModels.test_inventory_expansion_over_four_mib_refuses_bounded_original_inputs \
  InventoryModels.test_deep_malformed_manifest_refuses_with_finite_error \
  InventoryModels.test_public_inventory_operations_need_no_file_clock_or_process_operation \
  InventoryModels.test_inventory_errors_do_not_echo_private_input_and_output_has_no_log_hash_claim
```

Original result SHA256:
`58e64ec3104e6622618a2e44b3763a2ff8770bbcf52914e1b7c241096851761a`.

### R3 only corrected fixture

```text
implementation-r3 author-r3-malformed1 \
  InventoryModels.test_deep_malformed_manifest_refuses_with_finite_error
```

Original result SHA256:
`ef78a29b62024e977a05ccff6739b8a4a3408f4bd3774e3d6d7314e617e154cb`.
No aggregate replay occurred. Final38 distinct passing methods retain the exact
helper bytes and the explicit fixture-only input comparison described above.
