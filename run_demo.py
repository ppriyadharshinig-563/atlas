import os
import pandas as pd
import json
from stage1.atlas import StudyGraph, Atlas
from starter.schemas import Question

def create_mock_data():
    """Creates a temporary data folder with mock clinical data to test the system."""
    os.makedirs('data', exist_ok=True)

    # 1. Reference Ranges (Normal limits for labs)
    pd.DataFrame({
        'TESTCD': ['ALT', 'AST', 'BILI'],
        'SITEID': ['ALL', 'ALL', 'ALL'],
        'LLN': [0, 0, 0],
        'ULN': [40, 40, 1.2] # Upper Limit of Normal
    }).to_csv('data/reference_ranges.csv', index=False)

    # 2. Demographics (Patients)
    pd.DataFrame({
        'USUBJID': ['SUBJ-001', 'SUBJ-002'],
        'cut_available': [10, 10]
    }).to_csv('data/DM.csv', index=False)

    # 3. Lab Results (LB)
    # SUBJ-001 meets Hy's Law (ALT > 3xULN which is 120, BILI > 2xULN which is 2.4 within 14 days)
    # SUBJ-002 is normal
    pd.DataFrame({
        'USUBJID': ['SUBJ-001', 'SUBJ-001', 'SUBJ-002'],
        'LBTESTCD': ['ALT', 'BILI', 'ALT'],
        'LBSTRESN': ['150', '3.0', '25'], # 150 > 120 (3xULN), 3.0 > 2.4 (2xULN)
        'LBDTC': ['2024-01-01', '2024-01-05', '2024-01-01'], # 4 days apart (within 14 day window)
        'SITEID': ['S01', 'S01', 'S01'],
        'LBSEQ': [1, 2, 1],
        'cut_available': [10, 10, 10]
    }).to_csv('data/LB.csv', index=False)
    
    print("Mock data created in './data' folder.")

def test_atlas():
    print("\nInitializing StudyGraph and loading data...")
    # Load the graph with cut=10
    graph = StudyGraph('./data')
    graph.load(cut=10)
    
    print("Initializing ATLAS Solver...")
    atlas = Atlas(graph, cut=10)
    
    # Create a test question
    question = Question(id="test-1", text="Find subjects meeting Hy's Law criteria (ALT/AST and BILI).")
    
    print("\nSolving Query: 'Find subjects meeting Hy's Law criteria'")
    answers = atlas.solve([question])
    
    print("\nRESULT:")
    # Print the answer beautifully
    print(json.dumps(answers[0].__dict__, indent=2, default=lambda o: o.__dict__))

if __name__ == "__main__":
    create_mock_data()
    test_atlas()
