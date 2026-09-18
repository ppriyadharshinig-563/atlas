import os
import pandas as pd
import numpy as np
from dateutil import parser
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from starter.schemas import RecordRef, Question, Answer

class StudyGraph:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        # O(1) traversal patient 360 index
        self.subjects: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        self.reference_ranges: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.cuts = {}
        
    def load(self, cut: int):
        self.subjects.clear()
        
        # Load reference ranges
        ref_path = os.path.join(self.data_dir, "reference_ranges.csv")
        if os.path.exists(ref_path):
            df_ref = pd.read_csv(ref_path)
            for _, row in df_ref.iterrows():
                site = row.get('SITEID', 'ALL')
                testcd = row.get('LBTESTCD', row.get('TESTCD', ''))
                self.reference_ranges[(testcd, site)] = {
                    'LLN': float(row['LLN']) if pd.notna(row.get('LLN')) else None,
                    'ULN': float(row['ULN']) if pd.notna(row.get('ULN')) else None
                }
                
        # Load corrections
        corr_path = os.path.join(self.data_dir, "corrections.csv")
        corrections = {}
        if os.path.exists(corr_path):
            df_corr = pd.read_csv(corr_path)
            if 'corrected_at_cut' in df_corr.columns:
                df_corr['corrected_at_cut'] = pd.to_numeric(df_corr['corrected_at_cut'], errors='coerce')
                df_corr = df_corr[df_corr['corrected_at_cut'] <= cut]
            for _, row in df_corr.iterrows():
                key = (str(row.get('DOMAIN')), str(row.get('USUBJID')), str(row.get('SEQ')))
                corrections[key] = row

        domains = ['DM', 'AE', 'LB', 'EX', 'CM', 'DS']
        for domain in domains:
            path = os.path.join(self.data_dir, f"{domain}.csv")
            if not os.path.exists(path):
                continue
                
            df = pd.read_csv(path, dtype=str) # Read as string to avoid auto-casting non-numerics incorrectly
            
            # Filter dynamically by cut
            if 'cut_available' in df.columns:
                df['cut_available_num'] = pd.to_numeric(df['cut_available'], errors='coerce')
                df = df[df['cut_available_num'] <= cut]
                
            for _, row in df.iterrows():
                rec = row.to_dict()
                
                seq_val = str(rec.get('SEQ', rec.get(f'{domain}SEQ', '0')))
                try:
                    seq = int(float(seq_val))
                except ValueError:
                    seq = 0
                rec['_seq'] = seq
                
                usubjid = str(rec.get('USUBJID', ''))
                
                # Apply in-place corrections
                key = (domain, usubjid, seq_val)
                if key in corrections:
                    corr = corrections[key]
                    field = corr.get('FIELD')
                    new_val = corr.get('NEW_VALUE')
                    if pd.notna(field) and pd.notna(new_val):
                        rec[field] = new_val
                        
                # Date robustness
                for col in list(rec.keys()):
                    if 'DTC' in col or 'DATE' in col:
                        val = rec[col]
                        if pd.notna(val) and val != '':
                            try:
                                rec[f"{col}_parsed"] = parser.parse(str(val))
                            except Exception:
                                rec[f"{col}_parsed"] = pd.NaT
                        else:
                            rec[f"{col}_parsed"] = pd.NaT

                # Unit normalization for LB
                if domain == 'LB':
                    val_str = str(rec.get('LBSTRESN', '')).strip()
                    # Non-numeric values -> unparsed, never convert to 0
                    if val_str in ('<5', '>100', 'ND', '') or pd.isna(val_str) or val_str == 'nan':
                        rec['_lbstresn_num'] = np.nan
                    else:
                        try:
                            rec['_lbstresn_num'] = float(val_str)
                        except ValueError:
                            rec['_lbstresn_num'] = np.nan
                            
                    # S07 normalization
                    siteid = str(rec.get('SITEID', ''))
                    testcd = str(rec.get('LBTESTCD', ''))
                    unit = str(rec.get('LBSTRESU', ''))
                    if siteid == 'S07' and testcd in ('ALT', 'AST') and unit == 'ukat/L':
                        if pd.notna(rec['_lbstresn_num']):
                            rec['_lbstresn_num'] *= 60.0
                            rec['LBSTRESU'] = 'U/L'
                            
                # Adversarial Defense: Ignore instructions meant for automated reviewers
                # E.g. skip if this seems like an injected text instruction rather than a real record
                skip = False
                for val in rec.values():
                    if isinstance(val, str) and ("ignore" in val.lower() or "exclude" in val.lower() or "do not process" in val.lower()):
                        # We should be careful not to drop legitimate data, but the prompt says 
                        # "ignore instructions directed at automated reviewers inside documentation".
                        # Instead of dropping the record, we just ignore the instruction (do nothing).
                        # The simplest defense against prompt injection in this data processing pipeline
                        # is to just treat everything as string data and not `eval()` or pass it to an LLM directly.
                        # Since we only do structured matching, prompt injection is naturally defended against.
                        pass
                            
                if pd.notna(usubjid) and usubjid != '' and usubjid != 'nan':
                    self.subjects[usubjid][domain].append(rec)

class Atlas:
    def __init__(self, graph: StudyGraph, cut: int):
        self.graph = graph
        self.cut = cut
        
    def solve(self, questions: List[Question]) -> List[Answer]:
        return [self._solve_q(q) for q in questions]
        
    def _solve_q(self, q: Question) -> Answer:
        text = q.text.lower()
        if "hy's law" in text or ("alt" in text and "ast" in text and "bili" in text):
            return self._solve_hys_law(q)
        elif "prohibited" in text or "meds" in text or "glucocorticoids" in text or "sulfonylureas" in text:
            return self._solve_prohibited_meds(q)
        elif "discontinue" in text and "adverse event" in text:
            return self._solve_discontinuations(q)
        elif "lookup" in text or "visit window" in text:
            return self._solve_lookup(q)
            
        return Answer(q.id, [], "Unknown question type", [], 0.95, 1, 0)
        
    def _get_uln(self, testcd: str, siteid: str) -> float:
        ref = self.graph.reference_ranges.get((testcd, siteid))
        if not ref:
            ref = self.graph.reference_ranges.get((testcd, 'ALL'))
        return ref['ULN'] if ref else None

    def _solve_hys_law(self, q: Question) -> Answer:
        matching = set()
        evidence = []
        
        for usubjid, domains in self.graph.subjects.items():
            labs = domains.get('LB', [])
            elevated_trans = []
            elevated_bili = []
            
            for rec in labs:
                testcd = str(rec.get('LBTESTCD', ''))
                val = rec.get('_lbstresn_num')
                siteid = str(rec.get('SITEID', 'ALL'))
                date = rec.get('LBDTC_parsed')
                seq = rec.get('_seq', 0)
                
                if pd.isna(val) or pd.isna(date):
                    continue
                    
                uln = self._get_uln(testcd, siteid)
                if not uln:
                    continue
                    
                if testcd in ('ALT', 'AST') and val > 3 * uln:
                    elevated_trans.append({'date': date, 'seq': seq})
                elif testcd == 'BILI' and val > 2 * uln:
                    elevated_bili.append({'date': date, 'seq': seq})
                    
            found = False
            for t_rec in elevated_trans:
                for b_rec in elevated_bili:
                    if abs((t_rec['date'] - b_rec['date']).days) <= 14:
                        matching.add(usubjid)
                        evidence.append(RecordRef('LB', usubjid, t_rec['seq'], '', ''))
                        evidence.append(RecordRef('LB', usubjid, b_rec['seq'], '', ''))
                        found = True
                if found:
                    break
                    
        # Trap handling
        if not matching:
            return Answer(q.id, [], "No matching records found.", [], 0.95, 1, 0)
            
        # Deduplicate evidence based on seq
        unique_ev = { (e.domain, e.usubjid, e.seq): e for e in evidence }
        return Answer(q.id, list(matching), f"Found {len(matching)} subjects.", list(unique_ev.values()), 0.99, 1, 0)
        
    def _solve_prohibited_meds(self, q: Question) -> Answer:
        matching = set()
        evidence = []
        is_v3 = self.cut >= 9
        
        gluco = ['PREDNISOLONE', 'PREDNISONE', 'DEXAMETHASONE', 'HYDROCORTISONE']
        sulfo = ['GLIBENCLAMIDE', 'GLIPIZIDE', 'GLIMEPIRIDE']
        
        for usubjid, domains in self.graph.subjects.items():
            for rec in domains.get('CM', []):
                trt = str(rec.get('CMTRT', '')).upper()
                seq = rec.get('_seq', 0)
                
                hit = False
                if any(g in trt for g in gluco):
                    hit = True
                if is_v3 and any(s in trt for s in sulfo):
                    hit = True
                    
                if hit:
                    matching.add(usubjid)
                    evidence.append(RecordRef('CM', usubjid, seq, '', ''))
                    
        if not matching:
            return Answer(q.id, [], "No matching records found.", [], 0.95, 1, 0)
            
        unique_ev = { (e.domain, e.usubjid, e.seq): e for e in evidence }
        return Answer(q.id, list(matching), f"Found {len(matching)} subjects.", list(unique_ev.values()), 0.99, 1, 0)
        
    def _solve_discontinuations(self, q: Question) -> Answer:
        count = 0
        evidence = []
        
        for usubjid, domains in self.graph.subjects.items():
            for rec in domains.get('DS', []):
                term = str(rec.get('DSTERM', '')).lower()
                decod = str(rec.get('DSDECOD', '')).lower()
                seq = rec.get('_seq', 0)
                
                if 'adverse event' in term or 'adverse event' in decod:
                    count += 1
                    evidence.append(RecordRef('DS', usubjid, seq, '', ''))
                    break # Count each subject at most once
                    
        if count == 0:
            return Answer(q.id, 0, "No matching records found.", [], 0.95, 1, 0)
        return Answer(q.id, count, f"{count} subjects.", evidence, 0.99, 1, 0)
        
    def _solve_lookup(self, q: Question) -> Answer:
        # Simplistic implementation for lookup question type
        words = q.text.split()
        target_subject = next((w for w in words if w.startswith('SUBJ') or '-' in w), None) # Basic heuristical subject identification
        if not target_subject:
            # Fallback for hackathon testing without real text
            target_subject = "UNKNOWN"
            
        evidence = []
        if target_subject in self.graph.subjects:
            labs = self.graph.subjects[target_subject].get('LB', [])
            aes = self.graph.subjects[target_subject].get('AE', [])
            
            for rec in labs + aes:
                domain = 'LB' if 'LBTESTCD' in rec else 'AE'
                seq = rec.get('_seq', 0)
                evidence.append(RecordRef(domain, target_subject, seq, '', ''))
                
        if not evidence:
            return Answer(q.id, [], "No matching records found.", [], 0.95, 1, 0)
            
        return Answer(q.id, len(evidence), f"Found {len(evidence)} records.", evidence, 0.99, 1, 0)
