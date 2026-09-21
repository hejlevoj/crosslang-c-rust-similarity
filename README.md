# C↔Rust Code Similarity Research

This repository contains all resources for a research project on measuring and improving code similarity detection between C and Rust implementations of competitive programming problems. The goal is to enable machine learning models to recognize when two programs in different languages solve the same problem, even if their code structure diverges.

## What’s Included

- **Dataset:** 1857 pairs of C and Rust solutions to the same problems, cleaned and categorized by difficulty. Each pair includes the problem description and normalized code.
- **Code Analysis Pipeline:** Tools to preprocess, analyze, and auto-fix C and Rust code, producing quality metrics and standardized formatting for fair comparison.
- **Semantic Analysis Scripts:** Utilities to measure similarity between problem descriptions and code pairs, and to categorize dataset difficulty using state-of-the-art code embeddings.
- **Model Finetuning:** Scripts to train and evaluate UniXcoder models for cross-language code similarity, including both full finetuning and parameter-efficient LoRA adapters.

## Why This Matters

Understanding code similarity across languages is crucial for code search, plagiarism detection, and automated grading. This project provides a high-quality benchmark and tools for evaluating and improving cross-language code understanding.

## Repository Structure

- `dataset/` — Dataset, schema, and scripts for cleaning, description similarity, and difficulty categorization
- `code-evaluator/` — Static analysis pipeline for C and Rust code
- `dataset/finetune/` — UniXcoder finetuning and evaluation scripts

See the README in each subfolder for detailed instructions.

## Getting Started

1. Review the dataset and schema in `dataset/README.md` to understand the data format and sources.
2. Use the code analysis pipeline (`code-evaluator/README.md`) to preprocess and evaluate code pairs.
3. Run semantic analysis or model finetuning using scripts in `dataset/description-similarity/`, `dataset/categorization/`, and `dataset/finetune/`.

## Citation

If you use this dataset or code, please cite this repository. For questions or collaboration, open an issue or pull request.
