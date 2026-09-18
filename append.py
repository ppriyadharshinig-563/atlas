import os

with open(r'c:\Users\Priyadharashini G\OneDrive\Desktop\round1\stage1\atlas.py', 'a', encoding='utf-8') as f:
    f.write('''
    def _solve_dosing_error(self, q: Question) -> Answer:
        matching = set()
        evidence = []
        for usubjid, domains in self.graph.subjects.items():
            dm = domains.get('DM', [])
            if not dm: continue
            arm = str(dm[0].get('ARM', '')).upper()
            expected_dose = 10 if arm == 'DRUG' else 0 if arm == 'PLACEBO' else None
            
            for rec in domains.get('EX', []):
                dose_val = rec.get('EXDOSE', '')
                try:
                    dose = float(dose_val)
                except ValueError:
                    continue
                if expected_dose is not None and dose != expected_dose:
                    matching.add(usubjid)
                    evidence.append(RecordRef('EX', usubjid, rec.get('_seq', 0), '', ''))
        
        if not matching:
            return Answer(q.id, "none", "No dosing errors found.", [], 0.95, 1, 0)
        unique_ev = { (e.domain, e.usubjid, e.seq): e for e in evidence }
        return Answer(q.id, list(matching), f"Found {len(matching)} subjects.", list(unique_ev.values()), 0.99, 1, 0)

    def _solve_duplicate_subject(self, q: Question) -> Answer:
        seen = {}
        matching = set()
        evidence = []
        
        for usubjid, domains in self.graph.subjects.items():
            dm = domains.get('DM', [])
            if not dm: continue
            rec = dm[0]
            init = str(rec.get('DMINIT', ''))
            sex = str(rec.get('SEX', ''))
            brth = str(rec.get('BRTHDTC', ''))
            key = (init, sex, brth)
            
            if key in seen:
                matching.add(usubjid)
                matching.add(seen[key]['usubjid'])
                evidence.append(RecordRef('DM', usubjid, rec.get('_seq', 0), '', ''))
                evidence.append(RecordRef('DM', seen[key]['usubjid'], seen[key]['seq'], '', ''))
            else:
                seen[key] = {'usubjid': usubjid, 'seq': rec.get('_seq', 0)}
                
        if not matching:
            return Answer(q.id, "none", "No duplicates found.", [], 0.95, 1, 0)
        unique_ev = { (e.domain, e.usubjid, e.seq): e for e in evidence }
        return Answer(q.id, list(matching), f"Found {len(matching)} subjects.", list(unique_ev.values()), 0.99, 1, 0)

    def _solve_sae(self, q: Question) -> Answer:
        matching = set()
        evidence = []
        for usubjid, domains in self.graph.subjects.items():
            for rec in domains.get('AE', []):
                hosp = str(rec.get('AESHOSP', '')).upper()
                ser = str(rec.get('AESER', '')).upper()
                seq = rec.get('_seq', 0)
                
                # Treat SAE miscooded/unescalated as finding
                # AESHOSP=Y means SAE, if AESER=N it's an error. 
                # Or maybe if it's an SAE it just needs to be flagged.
                # Let's flag AESHOSP=Y and AESER=N.
                if hosp == 'Y' and ser == 'N':
                    matching.add(usubjid)
                    evidence.append(RecordRef('AE', usubjid, seq, '', ''))
        
        if not matching:
            return Answer(q.id, "none", "No SAE findings.", [], 0.95, 1, 0)
        unique_ev = { (e.domain, e.usubjid, e.seq): e for e in evidence }
        return Answer(q.id, list(matching), f"Found {len(matching)} subjects.", list(unique_ev.values()), 0.99, 1, 0)
''')
