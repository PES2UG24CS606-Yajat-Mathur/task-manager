# Mini-Project Part 3: test documents

| Deliverable | File |
|---|---|
| Updated test cases | [`Test_Case_Document.pdf`](Test_Case_Document.pdf) |
| Unit Test Report | [`Unit_Test_Report.pdf`](Unit_Test_Report.pdf) |
| System Validation Report | [`System_Validation_Report.pdf`](System_Validation_Report.pdf) |
| Code Coverage Report | [`Code_Coverage_Report.pdf`](Code_Coverage_Report.pdf) |
| Branch Coverage Report | [`Branch_Coverage_Report.pdf`](Branch_Coverage_Report.pdf) |

`evidence/` holds the raw results the documents are generated from: the JUnit file, coverage data,
system validation results, screenshots and the server log.

`evidence/v1.0/` keeps the results from before Sprint 3, so the reports can show what the fixes changed.
It also holds the output of the Sprint 3 tests run against the `v1.0` code.

## Regenerate everything

Windows (cmd), from the repository root, with the virtual environment active:

```bat
pip install -r requirements.txt -r requirements-dev.txt playwright cryptography
playwright install chromium

:: 1. Full unit test run, with line and branch coverage (coverage.py) and an HTML coverage site
pytest -q --cov=app --cov-branch --cov-report=json:docs/testing/evidence/coverage.json --cov-report=html:docs/testing/evidence/htmlcov --junitxml=docs/testing/evidence/junit.xml

:: 2. System validation: real server, real browser (about one minute). Optional for a coverage-only refresh
python system_tests/run_system_validation.py --out docs/testing/evidence

:: 3. Rebuild the five PDFs from those results
python system_tests/generate_reports.py
```

The "v1.0" coverage rows in the reports come from the saved measurements in `evidence/`, which used
`system_tests/stdlib_coverage.py`. Only the v1.0.1 row changes when you re-run step 1.

No results are typed by hand. Test case text, defects and observations are in `system_tests/test_case_catalog.py`.
`system_tests/stdlib_coverage.py` is a fallback for machines where coverage.py cannot be installed.
