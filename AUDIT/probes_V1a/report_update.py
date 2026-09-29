"""Audit-only per-row persistence helper (no application code touched)."""
from pathlib import Path
import re
P=Path(__file__).resolve().parents[1]/'VERIFY_V1a.md'
def append(row, section, verdict='CONFIRMED', severity='S1', frozen='No (ops); frozen dependencies', cross='ISSUE-076/077/079', option='A'):
    s=P.read_text()
    s=re.sub(r'^'+row+r' \|.*$',f'{row} | {verdict} | S1 | {severity} | {frozen} | {cross} | {option}',s,flags=re.M)
    s=s.replace(f'## {row} — not verified',f'## {row} — initial placeholder (superseded below)',1)
    assert f'## {row} — formal verdict' not in s
    s=s.replace('## New findings not in the audit\n',section.strip()+'\n\n## New findings not in the audit\n',1)
    done=re.findall(r'^C-\d+ \| (CONFIRMED|PARTIAL|REJECTED|DEVICE-EVIDENCE-NEEDED) \|',s,re.M)
    pending=[r for r in ('C-008','C-010','C-012','C-013') if f'## {r} — formal verdict' not in s]
    s=re.sub(r'\*\*Current status:.*?\*\*',f'**Current status: {len(done)} retained rows verified; {len(pending)} retained rows unverified; 9 rows reassigned to V1c.**',s,count=1)
    start=s.index('## Rows not verified or incomplete\n')
    s=s[:start]+'''## Rows not verified or incomplete

'''+('Retained, unverified (next order): **'+', '.join(pending)+'**.\n' if pending else 'Retained rows: **none unverified**. Device performance acceptance is not asserted; see individual limitations.\n')+'''
**Reassigned to V1c:** C-001, C-005, C-007, C-009, C-011, C-014, C-015, O-006, V-003. No V1a verification or verdict on these nine IDs.

Completed rows have twelve-heading formal sections and native offline evidence. Full test-suite or real-device readiness is not certified. Read coverage is itemized per row; execution of a test file is not represented as a complete line-by-line review of every unrelated test.

## Final counts

'''+''.join(f'- {v}: **{done.count(v)}**\n' for v in ('CONFIRMED','PARTIAL','REJECTED','DEVICE-EVIDENCE-NEEDED'))+f'- Retained unverified: **{len(pending)}**\n- Reassigned to V1c: **9**\n- Established new findings: **0**\n'
    P.write_text(s)
