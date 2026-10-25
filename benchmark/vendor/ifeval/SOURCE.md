# Vendored Google Instruction-Following Evaluation (IFEval)

- **Upstream Source**: https://github.com/google-research/google-research/tree/master/instruction_following_eval
- **License**: Apache License, Version 2.0 (see original header in each Python file)
- **Vendored Files**:
  - `instructions.py`
  - `instructions_registry.py`
  - `instructions_util.py`
  - `evaluation_lib.py`
- **Modifications**:
  - Relative/internal package imports adjusted from `instruction_following_eval` to `benchmark.vendor.ifeval`.
  - Added initialization in `instructions_util.py` to point `nltk.data.path` to vendored `nltk_data` directory.
