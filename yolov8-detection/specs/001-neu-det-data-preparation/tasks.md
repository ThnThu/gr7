# Tasks: Chuẩn bị dữ liệu NEU-DET cho Object Detection

**Input**: Design documents from `/specs/001-neu-det-data-preparation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/artifact-formats.md](./contracts/artifact-formats.md), [quickstart.md](./quickstart.md)

**Tests**: Bắt buộc. [plan.md](./plan.md) mục *Testing Strategy* và [quickstart.md](./quickstart.md)
§7 yêu cầu các nhóm test cho converter, validator, splitter, manifest và CLI end-to-end. Viết test
trước, xác nhận test fail, rồi mới implement.

**Organization**: Task được nhóm theo user story để mỗi story có thể implement và kiểm thử độc lập.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Có thể chạy song song (khác file, không phụ thuộc task chưa hoàn thành)
- **[Story]**: User story tương ứng (`US1`, `US2`, `US3`)
- Mọi task đều có đường dẫn file cụ thể

## Path Conventions

- Single project: `src/detection/` và `tests/` tại repository root
- Package dữ liệu: `src/detection/data/`
- Test: `tests/unit/` và `tests/integration/`
- Không tạo `configs/`; cấu hình chỉ đến từ CLI và được ghi trong manifest

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo package Python, entry point và fixture kiểm thử dùng chung.

- [x] T001 Create `pyproject.toml` at repo root with setuptools src layout, `requires-python = ">=3.11"`, runtime dependency `Pillow`, dev dependency `pytest`, console script `detection = "detection.cli:main"`, and `[tool.pytest.ini_options] testpaths = ["tests"]`
- [x] T002 [P] Create package skeleton in `src/detection/__init__.py`, `src/detection/data/__init__.py`, and test directories `tests/unit/`, `tests/integration/` (no committed image fixtures)
- [x] T003 [P] Create `tests/conftest.py` with deterministic fixture helpers: `make_image(path, size, color)`, `make_voc_xml(path, objects, size, filename=None)`, and `build_source_tree(tmp_path, subsets)` using Pillow; helpers must support multiple objects/classes, empty annotations, malformed XML, and cross-subset duplicate stems

**Checkpoint**: `pip install -e .` succeeds and `pytest -q` collects zero tests without import errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hạ tầng lõi dùng chung cho cả ba user story.

**⚠️ CRITICAL**: Không bắt đầu user story nào trước khi phase này hoàn tất.

- [x] T004 Implement fixed class catalogue in `src/detection/data/classes.py`: `CLASS_NAMES = {0: "crazing", 1: "inclusion", 2: "patches", 3: "pitted_surface", 4: "rolled-in_scale", 5: "scratches"}`; normalize source names with `strip().lower()` only; expose class lookup that returns/raises an `unknown_class` outcome with no fuzzy matching, aliases, remapping, or reordering; assert `class_id` is in `0..5`
- [x] T005 [P] Implement shared entities and enums in `src/detection/data/models.py` exactly per [data-model.md](./data-model.md): `SourceDataset`, `SourceSubset`, `ImageAsset`, `AnnotationAsset`, `SourceFingerprint`, `SourceObject`, `BoundingBox`, `MatchedSample`, `DuplicateGroup`, `SplitAssignment`, `Split`, `AnomalyRecord`, `ValidationReport`, `SplitManifest`; include the full anomaly taxonomy from §6 with exact `code`, `severity` (`error`, `warning`, `info`) and `scope`, plus `ANOMALY_CODES` as the ordered list used to emit zero-valued `anomaly_counts`. Enforce: `sample_id = "<subset>/<stem>"`, `read_only = True`, image extensions `.jpg/.jpeg/.png/.bmp/.tif/.tiff`, `present_classes` unique ascending with `[]` for zero objects (still eligible), `DuplicateGroup.group_id = "sha256:<hex>"`, and `Split` fields `target_ratio`, `actual_ratio`, `images`, `objects`, `image_counts_by_class`, `object_counts_by_class`, `source_subset_counts`, `assignments`
- [x] T006 Implement `src/detection/data/discovery.py` discovery and source fingerprint: identify direct child subsets with both `images/` and `annotations/`, or a single `root` subset; list images/XML in stable sorted relative-path order; ignore other extensions with `unsupported_file` info; fail with a configuration error when both sides are empty; a subset with only one of `images/`/`annotations/` is a structural error; implement `SourceFingerprint` over `(relative_path, size, sha256)` sorted by `relative_path`, `algorithm = "sha256"`, `tree_sha256`, `status`, `after_tree_sha256`, `verified_after_run`, `changed`, `error` per [data-model.md](./data-model.md) §3.5
- [x] T007 Implement `src/detection/data/discovery.py` pairing restricted to one source subset: exact stem, exactly one image and one XML per stem; never use `<filename>` and never pair `train/` with `validation/`; emit `missing_xml`, `missing_image`, or `ambiguous_pairing` anomalies without creating/renaming/deleting files
- [x] T008 Implement `src/detection/cli.py` argument parsing and pre-flight validation: `detection prepare --source PATH [--output PATH] [--seed INT] [--ratios T,V,TE] [--on-anomaly {fail,quarantine}] [--overwrite]`; `--source` required, `--output` default `data/processed/neu-det`, `--seed` default `42`, `--ratios` default `0.75,0.15,0.10`; reject ratios that are not three positive floats summing to `1.0` within `1e-9`; reject output equal to, inside, or a parent of source; reject existing non-empty output without `--overwrite`; define exit codes `0` success, `2` config/structure, `3` blocking data, `4` output exists, `5` I/O
- [x] T009 Implement `src/detection/data/manifest.py` shared JSON writing and config serialization: UTF-8, `indent=2`, `ensure_ascii=False`, trailing newline, atomic temp-file + `os.replace`; build the `config` object with `seed`, `ratios`, `on_anomaly`, `stratification = "multilabel_iterative"`, `duplicate_policy = "content_group_atomic"`, and the fixed `class_mapping` 0–5
- [x] T010 [P] Create the Foundational unit tests in `tests/unit/`: `test_classes.py` (exact 6-class order, `strip().lower()` normalization with mixed case/extra spaces, unknown names producing `unknown_class`, rejection of aliases/fuzzy matches), `test_models.py` (anomaly taxonomy codes/severity/scope, `sample_id`, `read_only`, image extensions, sorted unique `present_classes`, `DuplicateGroup.group_id`), `test_discovery.py` (subset discovery, sorted assets, unsupported files, structural errors, source fingerprint before/after, same-subset pairing only, cross-subset stems not paired, `missing_xml`/`missing_image`/`ambiguous_pairing`, no source writes), `test_cli.py` (defaults, ratio validation, source/output safety, existing output and `--overwrite`, exit-code mapping), and `test_manifest.py` (atomic UTF-8 JSON with indent 2, `ensure_ascii=False`, trailing newline, temp-file + `os.replace`, and the shared `config` object with fixed class mapping)

**Checkpoint**: Discovery, pairing, class mapping, shared entities, CLI validation and atomic JSON writing are usable and covered by tests; no user story work has started.

---

## Phase 3: User Story 1 - Chuyển annotation nguồn sang định dạng huấn luyện detection (Priority: P1) 🎯 MVP

**Goal**: Chuyển annotation Pascal VOC thành nhãn YOLO, copy ảnh sang output riêng, giữ nguyên dữ liệu nguồn.

**Independent Test**: Tạo source tổng hợp trong `tmp_path`, chạy `detection prepare`; mỗi ảnh nguồn có đúng một file nhãn, mọi `class_id` nằm trong `0..5`, annotation rỗng tạo file nhãn 0 byte, và hash cây nguồn trước/sau giống hệt.

### Tests for User Story 1

> **NOTE: Viết test trước, xác nhận FAIL trước khi implement.**

- [x] T011 [P] [US1] Create `tests/unit/test_converter.py` covering multiple objects, multiple classes per image (`present_classes` contains all class IDs), empty annotation, object order preserved from XML, exactly 6 decimal places, `w`/`h` in `(0, 1]`, `cx`/`cy` in `[0, 1]`, no clipping, and whole-sample failure when any object is invalid
- [x] T012 [US1] Extend `tests/integration/test_prepare_dataset.py` with the US1 conversion journey: synthetic source with at least 3 images (one empty annotation) and mixed classes; assert `images/train` and `labels/train` counts, one label per image, label content format, empty 0-byte label, and unchanged source tree hash; this test is expected to fail until T016

### Implementation for User Story 1

- [x] T013 [US1] Implement VOC XML parsing and YOLO conversion in `src/detection/data/converter.py`: parse `<annotation>`, `<object>`, `<name>`, and `<bndbox>` coordinates; reject non-finite numbers; compute normalized `cx = (xmin + xmax) / 2 / image_width`, `cy = (ymin + ymax) / 2 / image_height`, `w = (xmax - xmin) / image_width`, `h = (ymax - ymin) / image_height`; emit `class_id cx cy w h` with 6 decimals in original `<object>` order; produce an empty label for zero objects; never clip, never modify XML, and mark the whole sample invalid if any object fails
- [x] T014 [US1] Implement image-level verification in `src/detection/data/validator.py`: open and `verify()` images with Pillow, read actual `width`/`height`, compute SHA-256 of image content, mark unreadable images `corrupt_image`, and emit `size_mismatch` warning with actual size used for normalization
- [x] T015 [US1] Implement the conversion stage and reusable writer in `src/detection/data/pipeline.py`: run discover → pair → convert, call the image checks, and copy images with `shutil.copy2` plus write labels into `images/<split>/` and `labels/<split>/`; apply deterministic output names (keep stem if unique, otherwise `<subset>_<stem>`, otherwise add first 8 SHA-256 chars); take a source fingerprint before and after the run; for US1 use `train` as the interim single-split target until US3 supplies real assignments; never write, rename, move, or delete anything under `--source`
- [x] T016 [US1] Wire `src/detection/cli.py` to the US1 conversion path: parse args, call the pipeline, print a concise summary, return exit code `0` on success, `2` for config/structure errors, `3` when unpaired/blocking input exists (no silent drop), and `5` for unexpected I/O; do not emit `validation_report.json` or `split_manifest.json` yet

**Checkpoint**: US1 is independently functional: converted images/labels exist, source is unchanged, and no data is dropped without a non-zero exit and stderr explanation.

---

## Phase 4: User Story 2 - Kiểm tra tính toàn vẹn dữ liệu trước khi huấn luyện (Priority: P2)

**Goal**: Tạo `validation_report.json` đầy đủ với accounting, phát hiện lỗi class/bbox/cặp ảnh–XML/ảnh trùng, áp dụng gate `fail` hoặc `quarantine`, copy rejected mirror nguồn và bảo vệ dataset cũ khi `--overwrite`.

**Independent Test**: Đưa các mẫu lỗi đã biết vào source tổng hợp; report liệt kê đúng từng mẫu với code, path, reason; mẫu hợp lệ không bị báo sai; `fail` dừng trước split với exit `3` và report-only output; `quarantine` copy mẫu paired lỗi sang `rejected/` mirror nguồn, báo unpaired mà không copy, và giữ `accounting_ok = true`; chạy lại với `--overwrite` không làm mất dataset cũ khi input mới lỗi.

### Tests for User Story 2

> **NOTE: Viết test trước, xác nhận FAIL trước khi implement.**

- [x] T017 [P] [US2] Create `tests/unit/test_validator.py` for the **sample-validation orchestrator and duplicate audit**, reusing the existing discovery/pairing tests instead of duplicating them: assert the orchestrator calls/reuses `verify_image()` and `convert_annotation()` behaviour, covers malformed `invalid_xml`, `unknown_class`, `invalid_bbox` (`xmin >= xmax`, `ymin >= ymax`, negative, out-of-bounds, non-numeric, boxes rounding to zero width/height), `corrupt_image`, `size_mismatch` (both image and XML paths), `filename_mismatch` (basename comparison; pairing unchanged), and `empty_annotation`; assert no clipping and whole-sample rejection when one object fails. Add duplicate-audit tests: only eligible samples are grouped by SHA-256; one `duplicate_content` per member with `group_id`, `sha256`, `member_count`, `labels_consistent`; consistent labels warning and retained; conflicting labels error for every member; normalized `(class_id, cx, cy, w, h)` multiset ignores XML object order; deterministic anomaly ordering. Keep `missing_xml`/`missing_image`/`ambiguous_pairing`/cross-subset pairing tests in `tests/unit/test_discovery.py`. (Depends: T010, T013, T014)
- [ ] T018 [P] [US2] Extend `tests/unit/test_manifest.py` with report-schema and writer tests: required fields per [contracts/artifact-formats.md](./contracts/artifact-formats.md) §3; `config` reflects the CLI `seed`, `ratios`, `on_anomaly`; `anomaly_counts` contains every known code including zeros; `summary.unwritten_samples` exists and `summary.accounted_images = written_samples + quarantined_samples + unwritten_samples + unpaired_images`; `accounting_ok` matches that equation; `gate.blocking_errors`/`warnings` count error/warning records only; `pass_with_quarantine` may have `blocking_errors > 0`; `gate.status` is one of `pass`, `pass_with_quarantine`, `fail`; `source.fingerprint.status` distinguishes `verified_unchanged`/`changed`/`unavailable` and never reports unperformed checks as changed; anomalies sort deterministically; `write_validation_report` writes atomically and supports first write + final update. (Depends: T009)
- [ ] T019 [US2] Extend `tests/integration/test_prepare_dataset.py` with US2 scenarios **and update the accepted US1 assertions**: successful US1 runs now create `validation_report.json` (manifest still absent until US3); blocking data errors exit `3` and leave report-only output (no `images/`/`labels/`); quarantine copies paired image + XML to `rejected/images/<subset>/<relative-path>` and `rejected/annotations/<subset>/<relative-path>`, reports `pass_with_quarantine`, and does not copy unpaired assets; all-quarantined exits `3` with report + `rejected/`; unpaired errors with at least one eligible sample still exit `0`; output equal to/inside/a parent of source exits `2` without writes; a subset with only `images/` or only `annotations/` exits `2`; unsupported extension is ignored with `unsupported_file` info; existing output without `--overwrite` exits `4`; `--overwrite` with failing new input preserves the prior dataset at `<output>.previous` and leaves report-only output; retry without `--overwrite` exits `4`, retry with `--overwrite` safely replaces the report; source-change-after-write exits `3` with report and no dataset; update `test_rerun_with_overwrite_is_deterministic` so it compares dataset artifacts or normalizes `generated_at` instead of byte-comparing the report; source tree hash unchanged in every case; expected to fail until T022/T023/T024. (Depends: T016, T018)

### Implementation for User Story 2

- [x] T020 [US2] Implement the **sample-validation orchestrator** in `src/detection/data/validator.py`: call `verify_image()` for image integrity/size/SHA-256 and `convert_annotation()` for XML/class/bbox/normalized labels; do not duplicate XML parsing, class mapping or bbox validation in the orchestrator or pipeline. In the orchestrator, compare XML `declared_size` with the actual image size (warning `size_mismatch`, both image and XML paths, actual size used) and compare the `<filename>` basename with the paired image filename (warning `filename_mismatch`, both paths, pairing unchanged). Compute `present_classes` from conversion, drive `discovered → paired → valid|invalid`, and invalidate the whole sample when any object fails; never clip or repair. This takes over `size_mismatch` ownership from the current pipeline helper; `verify_image()` stays image-only. (Depends: T014, T013, T017)
- [x] T021 [US2] Implement duplicate-content audit in `src/detection/data/validator.py`: audit only eligible validated samples; group at least two members by SHA-256 into an in-memory `DuplicateGroup`; set `labels_consistent` by comparing the order-insensitive multiset of `(class_id, normalized cx, cy, w, h)` (6-decimal values), ignoring XML object order; emit exactly one `duplicate_content` per member with `group_id`, `sha256`, `member_count`, `labels_consistent`; consistent labels → warning and retain group; conflicting labels → error for the whole group; never drop a group or member silently; do not add `duplicate_groups` to the report. (Depends: T020)
- [ ] T022 [US2] Implement `write_validation_report` in `src/detection/data/manifest.py`: schema `"1.0"`, `feature = "001-neu-det-data-preparation"`, UTC ISO-8601 `generated_at`, `source` with root/subsets/fingerprint status, `config` built from the actual CLI `seed`, `ratios`, `on_anomaly`, full `summary` including `unwritten_samples`/accounting, `gate` with `status`/`blocking_errors`/`warnings`, and `anomalies` sorted deterministically (`code`, `paths`, `sample_id`, object index, `reason`); write atomically, support first write after gate and final update after verify, and fail with exit `5` when the report cannot be written. (Depends: T018, T009)
- [ ] T023 [US2] Implement gate, quarantine, safe output handling, report lifecycle and fingerprint checks in `src/detection/data/pipeline.py`: `--on-anomaly fail` stops before split/write with exit `3` and report-only failure output; `--on-anomaly quarantine` removes paired error samples (including a conflicting duplicate group as a whole) from the split pool, copies raw image + XML to `rejected/images/<subset>/<relative-path>` and `rejected/annotations/<subset>/<relative-path>` with `shutil.copy2`, never copies unpaired assets, sets `pass_with_quarantine` when at least one eligible sample remains, and exits `3` when none remains (report + `rejected/`, no images/labels/manifest); enforce the accounting equation at every report write (samples not yet written count as `unwritten_samples` in the first report, including invalid paired samples in fail mode). Use staging (`<output>.staging`) plus `<output>.previous` for `--overwrite`: validate before replacing anything, preserve the previous dataset on failure, commit only after final report/verify, and keep unrelated output files. Recompute the source fingerprint after validation even in fail mode and after write/verify; distinguish `verified_unchanged`, `changed` (`source_tree_changed`, exit `3`) and `unavailable` (no false `source_tree_changed`, exit `5`); update the report on source/verify failure when possible; clean up rejected/interim artifacts on failure. (Depends: T020, T021, T022; T019 tests)
- [ ] T024 [US2] Finalize CLI integration and exit-code mapping in `src/detection/cli.py`: pass `seed`, `ratios` and `on_anomaly` through `ConversionOptions`/pipeline to the report builder; map `0` success (`pass`/`pass_with_quarantine`), `2` usage/config/structure, `3` blocking data/all-quarantined/source changed/split or accounting invariant, `4` output exists without `--overwrite` (including report-only output), `5` unexpected I/O including report-write failure and fingerprint `unavailable`; write detailed errors to stderr and keep structured results in JSON, not stdout. (Depends: T023, T008)

**Checkpoint**: US1 and US2 work independently; the report fully explains every dropped or rejected sample, accounting balances, rejected copies mirror the source, report lifecycle and fingerprint statuses are correct, overwrite preserves the prior dataset on failure, and the gate/exit-code behavior matches the CLI contract.

---

## Phase 5: User Story 3 - Tạo split tái lập và bản ghi dữ liệu đã xử lý (Priority: P3)

**Goal**: Chia 75/15/10 multi-label, group-aware, seed 42; ghi `split_manifest.json` sau khi verify.

**Independent Test**: Với 1.800 sample tổng hợp, split cho đúng `1350/270/180`; chạy hai lần với cùng seed cho danh sách sample giống hệt; giao theo `sample_id`, `output_image`, `sha256` rỗng; nhóm ảnh trùng quá lớn tạo `split_distribution_deviation` và tỷ lệ thực tế được ghi trong manifest.

### Tests for User Story 3

> **NOTE: Viết test trước, xác nhận FAIL trước khi implement.**

- [ ] T025 [P] [US3] Create `tests/unit/test_splitter.py` using in-memory `MatchedSample` objects (no real images): 1.800 samples split into exactly `1350/270/180` by largest-remainder with tie-break `train`, `validation`, `test`; seed `42` reproducibility across two runs; multi-label stratification uses all `present_classes`; `present_classes = []` samples remain eligible and are allocated to remaining capacity; duplicate groups stay atomic; pairwise disjoint checks by `sample_id`, output path and SHA-256; oversized duplicate group triggers `split_distribution_deviation` with actual ratios recorded; a class missing from a split triggers `split_class_absent`; ratios that are non-positive or do not sum to `1.0` are rejected
- [ ] T026 [P] [US3] Extend `tests/unit/test_manifest.py` with `split_manifest.json` tests: required fields per [contracts/artifact-formats.md](./contracts/artifact-formats.md) §4, `classes` exactly 0–5 in order, `totals` and per-split counts, `actual_ratio = images / totals.images`, `assignments` sorted by `sample_id`, `duplicate_groups`, all eight `invariants` keys, and no manifest write when any invariant is false
- [ ] T027 [US3] Extend `tests/integration/test_prepare_dataset.py` with the end-to-end US3 journey: synthetic source, run twice with the same seed and compare per-split sample lists, verify manifest exists and split lists are disjoint, verify `images/<split>` and `labels/<split>` counts match, verify invalid ratios (non-positive, wrong count, sum not `1.0`) exit `2`, and verify no manifest is written when source verification or a split invariant fails; expected to fail until T032

### Implementation for User Story 3

- [ ] T028 [US3] Implement split sizing and multi-label stratification in `src/detection/data/splitter.py`: compute target sizes with largest-remainder over eligible samples (default `0.75/0.15/0.10`, tie-break `train`, then `validation`, then `test`); represent each sample by the full `present_classes` set; prioritize rare classes, compute remaining demand per split/class, assign to the split with highest total demand, and break ties with a local `random.Random(seed)` plus sorted `sample_id` (no global random state); allocate `present_classes = []` samples to remaining capacity deterministically
- [ ] T029 [US3] Implement duplicate-group atomic assignment and split invariants in `src/detection/data/splitter.py`: assign every `DuplicateGroup` as a unit to one split, prefer the split that best preserves ratios, and when atomicity makes exact targets impossible emit `split_distribution_deviation` and report actual ratios; emit `split_class_absent` when a class is missing from a split; verify INV-01 through INV-07 (all eligible assigned exactly once, no overlap by `sample_id`/`output_image`/`sha256`, totals equal eligible count, all group members together) plus `no_cross_subset_pairing` and fixed class mapping
- [ ] T030 [US3] Implement `write_split_manifest` in `src/detection/data/manifest.py`: schema `"1.0"`, `dataset` with name/source root/source fingerprint/subsets, `config` from T009, `classes` 0–5, `totals`, `splits` with `target_ratio`, `actual_ratio`, counts and sorted `assignments`, `duplicate_groups`, and all eight `invariants`; write only after split/write/source verification succeeds, atomically, and never on invariant failure
- [ ] T031 [US3] Implement the split → write → verify stage in `src/detection/data/pipeline.py`: call the splitter on eligible samples, copy images and write labels into `images/<split>/` and `labels/<split>/`, update `SplitAssignment` output paths, verify one label per image and expected file counts, recheck disjointness and duplicate atomicity, recompute the source fingerprint, update `validation_report.json` last, and write `split_manifest.json` only when every invariant passes; otherwise exit `3` without a manifest
- [ ] T032 [US3] Finalize `src/detection/cli.py` for the full contract: enforce `--ratios 0.75,0.15,0.10` default and `--seed 42`, validate three positive ratios summing to `1.0` within `1e-9` (exit `2` otherwise), run discover → pair → validate → duplicate audit → gate → split → write → verify, keep output/source separation checks before any write, and ensure reruns with the same data/config/seed produce identical split lists

**Checkpoint**: All three user stories work end-to-end; 75/15/10 is deterministic, duplicate-safe and fully recorded in `split_manifest.json`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Xác nhận quickstart, hiệu năng, bất biến nguồn và tính nhất quán tài liệu.

- [ ] T033 [P] Validate every command and expected output in `specs/001-neu-det-data-preparation/quickstart.md` against a synthetic dataset in `tmp_path`; fix only the documentation if a command, exit code or expected count is wrong
- [ ] T034 [P] Run a performance smoke test using `tests/conftest.py` helpers to generate a 1.800-image synthetic tree (small 64×64 JPEGs), invoke `detection prepare` from `src/detection/cli.py`, and confirm the full pipeline finishes under 10 minutes with copy-only image handling and no pixel transformations
- [ ] T035 Run `pytest -q` across `tests/unit/` and `tests/integration/`; confirm all required groups are covered, no test uses the real NEU-DET dataset or network, and source fingerprints are unchanged in every integration run
- [ ] T036 [P] Audit documentation consistency across `specs/001-neu-det-data-preparation/spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, and this `tasks.md`: confirm 75/15/10, seed 42, `1350/270/180`, fixed class mapping, duplicate atomicity and `split_distribution_deviation` are stated identically; do not change Feature 002

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Không phụ thuộc; bắt đầu ngay
- **Foundational (Phase 2)**: Phụ thuộc Setup; chặn toàn bộ user story
- **US1 (Phase 3)**: Phụ thuộc Foundational
- **US2 (Phase 4)**: Phụ thuộc US1 (dùng converter, image checks và writer của US1)
- **US3 (Phase 5)**: Phụ thuộc US2 (dùng gate, report và duplicate audit của US2)
- **Polish (Phase 6)**: Phụ thuộc US1–US3

### User Story Dependencies

- **US1 (P1)**: Độc lập sau Foundational; tạo converted dataset với split tạm `train`
- **US2 (P2)**: Cần output conversion của US1 để kiểm tra; test độc lập bằng fixture lỗi riêng
- **US3 (P3)**: Cần pool sample đã validate của US2; test splitter độc lập bằng sample in-memory

> Pipeline là chuỗi xử lý dữ liệu nên US2/US3 dùng lại stage của story trước. Không chạy song song
> ba story trên cùng pipeline; chỉ chạy song song các task khác file trong cùng phase.

### Within Each User Story

- Test phải được viết và FAIL trước khi implement
- Models/entities trước service; converter/validator trước pipeline; pipeline trước CLI wiring
- US2: T017/T018 (test) → T019 (integration) → T020 (validator orchestrator) → T021 (duplicate
  audit) → T022 (report writer) → T023 (gate/quarantine/staging/fingerprint) → T024 (CLI)
- Hoàn tất checkpoint của story trước khi chuyển priority tiếp theo
- Integration test của story phải chạy được trên fixture tổng hợp, không dùng dataset thật

### Parallel Opportunities

- Setup: T002 và T003 sau T001
- Foundational: T004 và T005 song song; sau T005 có thể chạy T006, T008, T009; T007 sau T006; T010 sau T004
- US2: T017 và T018 song song (khác file); T019 sau T016/T018; T020 sau T017; T021 sau T020;
  T022 sau T018; T023 sau T020–T022; T024 sau T023
- US3: T025 và T026 song song (khác file); T027 sau T024
- Polish: T033, T034, T036 song song sau khi pipeline hoàn tất; T035 chạy cuối

---

## Parallel Example: Foundational

```bash
# Sau khi Setup hoàn tất, chạy song song hai module độc lập:
Task: "Implement fixed class catalogue in src/detection/data/classes.py"
Task: "Implement shared entities and enums in src/detection/data/models.py"

# Sau T005, các task khác file có thể chạy song song:
Task: "Implement discovery and source fingerprint in src/detection/data/discovery.py"
Task: "Implement CLI parsing and pre-flight validation in src/detection/cli.py"
Task: "Implement atomic JSON writing and config serialization in src/detection/data/manifest.py"
```

---

## Parallel Example: User Story 2

```bash
# Hai test khác file, viết trước khi implement:
Task: "Create tests/unit/test_validator.py"
Task: "Extend tests/unit/test_manifest.py with report-schema tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Hoàn tất Phase 1: Setup
2. Hoàn tất Phase 2: Foundational
3. Hoàn tất Phase 3: US1
4. **STOP và VALIDATE**: chạy `tests/unit/test_converter.py`, `tests/unit/test_classes.py` và
   `tests/integration/test_prepare_dataset.py` (US1); xác nhận source hash không đổi
5. MVP tạo ra converted dataset dùng được dưới split tạm `train`, chưa có report/split đầy đủ

### Incremental Delivery

1. Setup + Foundational → nền tảng sẵn sàng
2. US1 → converted images/labels + source bất biến → kiểm thử độc lập
3. US2 → validation report, gate `fail`/`quarantine`, accounting → kiểm thử độc lập
4. US3 → split 75/15/10, manifest, invariants → kiểm thử độc lập và end-to-end
5. Polish → quickstart, hiệu năng, full test suite, đồng bộ tài liệu

### Parallel Team Strategy

Với nhiều người:

1. Cả nhóm hoàn tất Setup + Foundational
2. Sau Foundational:
   - Developer A: US1 (converter, image checks, writer)
   - Developer B: viết test US2/US3 trên fixture in-memory (không sửa pipeline)
3. Sau US1: Developer A + B cùng US2; sau US2 cùng US3
4. Không sửa đồng thời `src/detection/data/pipeline.py`, `src/detection/cli.py` hoặc
   `tests/integration/test_prepare_dataset.py` bởi hai người

---

## Notes

- `[P]` chỉ dùng khi task khác file và không phụ thuộc task chưa xong
- Mọi task phải giữ nguyên: class mapping 0–5, source read-only, copy ảnh (không hard link/symlink),
  duplicate group nguyên tử, `split_distribution_deviation` khi lệch tỷ lệ, manifest chỉ ghi sau verify
- US2 phải giữ: accounting `written + quarantined + unwritten + unpaired_images == source_images`;
  rejected chỉ sample paired, mirror path nguồn; report atomic first write/final update; fingerprint
  ba trạng thái; overwrite staging/backup; unpaired không copy; all-quarantined fail nhưng vẫn có
  report + rejected; CLI truyền đủ `seed`/`ratios`/`on_anomaly` vào report
- Không huấn luyện, không đánh giá, không tạo `dataset.yaml`, không thay đổi Feature 002
- Không commit ảnh mẫu; mọi fixture nằm trong `tmp_path`
- Commit sau mỗi task hoặc nhóm task logic; dừng tại checkpoint để validate story độc lập
