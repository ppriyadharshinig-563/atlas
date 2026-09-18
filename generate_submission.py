import json
import os
import time
from stage1.atlas import StudyGraph, Atlas
from starter.schemas import Question

def generate():
    # 1. Generate graph_stats.json
    print("Building StudyGraph...")
    start_time = time.time()
    sg = StudyGraph('./hackathon-data/data')
    import pandas as pd
    cuts_df = pd.read_csv('./hackathon-data/data/cuts.csv')
    max_cut = int(cuts_df['cut'].max())
    stats = sg.build(cut=max_cut)
    
    # Optional ms override for exactness
    stats['ms'] = int((time.time() - start_time) * 1000)
    
    with open('graph_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print("Created graph_stats.json")
    
    # 2. Generate stage1_public.json
    print("Running Atlas on public questions...")
    atlas = Atlas(sg)
    
    public_questions = [
        Question("Q001", "Find subjects meeting Hy's Law criteria (ALT/AST and BILI)."),
        Question("Q031", "dosing error S01 wrong dose?"),
    ]
    
    answers = atlas.solve(public_questions)
    
    with open('stage1_public.json', 'w') as f:
        json.dump([a.__dict__ for a in answers], f, default=lambda o: o.__dict__, indent=2)
    print("Created stage1_public.json")

if __name__ == '__main__':
    generate()
