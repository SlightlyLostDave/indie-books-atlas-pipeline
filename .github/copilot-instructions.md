# Custom Instruction for Indie Books Atlas Data Pipeline

## Project Overview

This is a python project that implements a data pipeline for the Indie Books Atlas website. The pipeline is responsible for extracting data from various sources, transforming it into a consistent format, and loading it into a database for use in a next.js application.

## Coding Standards

- This is a Python project.
- Follow PEP 8 for formatting and naming.
- Keep functions small and single-purpose.
- Use type annotations for all public functions and return values.
- Write clear docstrings for modules, classes, and public functions.
- Prefer descriptive variable names and avoid abbreviations.
- Keep parsing, transformation, and I/O logic separated.
- Use structured logging via the standard `logging` module.
- Prefer immutability and pure functions where practical.
- Write tests with `pytest`; put them in the `tests/` directory.
- Keep tests deterministic and mock external API calls.
- Use a formatter/linter such as `black`, `ruff`, and `isort` if configured.
- Avoid committing secrets or credentials.
