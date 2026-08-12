# Vendored SWE-bench Pro grading harness

`run_scripts.tar.gz` contains the **official** per-instance grading scripts from
[`scaleapi/SWE-bench_Pro-os`](https://github.com/scaleapi/SWE-bench_Pro-os)
(MIT License, Copyright (c) 2026 Scale AI, Inc).

## Contents

Extracted layout (one dir per instance id):

```
run_scripts/{instance_id}/run_script.sh   # official test runner for that instance
run_scripts/{instance_id}/parser.py       # official stdout/stderr -> output.json parser
```

`grader.py` extracts this tarball once (to a per-machine temp cache) and feeds
each instance's two scripts into the sandbox, reproducing the upstream
`swe_bench_pro_eval.py` evaluation exactly. The instance's `base_commit`,
`before_repo_set_cmd`, `selected_test_files_to_run`, `fail_to_pass` and
`pass_to_pass` come from the HuggingFace dataset row (not from here).

## Provenance / how to refresh

Produced by cloning the upstream repo and archiving its `run_scripts/`
directory (dropping `instance_info.txt`, which grading does not use):

```bash
git clone --depth 1 https://github.com/scaleapi/SWE-bench_Pro-os.git
cd SWE-bench_Pro-os
tar -czf run_scripts.tar.gz --exclude='instance_info.txt' run_scripts
```

Only the MIT-licensed grading scripts are vendored — no dataset content, no
Docker images. This keeps A2E standalone (the Standalone red line) while using
the authoritative grader.
