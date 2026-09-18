# Problem 1 — ATLAS Submission

## Understanding
This project implements the "Study Sentinel" (ATLAS) for the STUDY-042 Phase III Diabetes Trial. The objective is to build an automated clinical reasoning agent capable of indexing synthetic trial data into a "Patient 360" view. The agent must evaluate clinical rules (e.g., Hy's Law, Prohibited Meds, Dosing Errors, SAEs) against the dataset, strictly adhering to protocol versions and data cuts, while identifying planted findings within a strict hard time limit of 120 seconds per query.

## Architecture
The system is divided into two core components:
1. **`StudyGraph` (Data Indexer)**: Ingests CSV files, applies data cuts/corrections dynamically, and normalizes values before loading them into an in-memory dictionary-based patient index. 
2. **`Atlas` (Query Solver)**: A deterministic, rule-based QA agent that evaluates specific clinical conditions against the `StudyGraph` and returns standardized `Answer` objects containing exact `RecordRef` citations.

## Tech Stack
- **Language**: Python 3
- **Dependencies**: `pandas` (for robust CSV loading/filtering) and `python-dateutil` (for flexible date parsing).
- **Format**: All outputs map to the required `starter.schemas` dataclasses.

## Data Handling
Data ingestion is explicitly designed to handle anomalies and adversarial traps:
- **Missing/Non-numeric Values**: Values like `<5`, `>100`, or `ND` are treated as unparsed `NaN` and are never incorrectly cast to `0`. 
- **Unit Normalization**: Automatically converts Site S07's ALT and AST values from `µkat/L` to standard `U/L` using the 1:60 scale factor.
- **Data Cuts & Corrections**: Filters records strictly where `cut_available <= target_cut`. Dynamically applies inline updates from `corrections.csv` over the target rows before indexing.

## Documents
The solver evaluates records against specific rules mapped from the provided manuals and protocols:
- **Protocol Versions (V1/V2/V3)**: Logic adapts dynamically based on the active cut. E.g., identifies *Systemic Glucocorticoids* as prohibited meds across all cuts, and actively incorporates *Sulfonylureas* for cuts ≥ 9 (Protocol V3).
- **Adversarial Instructions**: Ignores misleading natural language commands injected into the documentation (e.g., instructions to ignore Site S03/S07) by parsing only strictly typed schemas.

## When the answer is nothing
When a query returns zero valid matching subjects or records (e.g., searching for dosing errors where none exist), the solver gracefully aborts and returns an exact JSON format with `answer: "none"`, an empty `evidence` array, and a confidence score of `0.95`. This explicitly fulfills the hackathon requirement to "say 'none' when the answer is none" without guessing or hallucinating false citations.

## Graph
The knowledge graph is modeled as an in-memory "Patient 360" hierarchical index. 
- **Structure**: `self.subjects[usubjid][domain]` stores chronological lists of records for each patient. 
- **Performance**: Provides pure `O(1)` node traversal for patient-specific queries, avoiding repeated disk reads or whole-table DataFrame scans, ensuring latency stays well under the 120-second threshold.

## Limitations
- **Natural Language Parsing**: The QA agent relies on fast heuristic keyword matching (e.g., `"hy's law" in query`, `"dosing error" in query`) rather than an LLM-based intent parser to guarantee low latency and deterministic correctness.
- **Memory Consumption**: Because the entire `StudyGraph` is loaded in memory for fast `O(1)` access, massive Phase III trials with millions of records could potentially hit RAM limits without disk-backed chunking.
