"""Prepare the medical content backlog without auto-publishing external data.

Usage:
    python backfill_medical_quality.py

The script:
- ensures every symptom has the standard follow-up/care template,
- reports public-source gaps,
- queues ICD-11 candidates when WHO credentials are configured,
- prints Search Console/Trends content gaps already imported.
"""
import json
import os

import health_library
import medical_knowledge as mk
import medical_taxonomy
import symptom_guidance
import content_priority


def main():
    guidance=symptom_guidance.backfill_all()
    source_gaps=health_library.source_quality_audit()
    icd={"queued":0,"errors":[]}
    if os.getenv("WHO_ICD_CLIENT_ID") and os.getenv("WHO_ICD_CLIENT_SECRET"):
        # Queue both diseases and symptoms. Exact mappings remain candidates
        # until a human approves them in Admin. A deployment can cap the
        # number of external requests per run with ICD_BACKFILL_LIMIT.
        limit=max(1,int(os.getenv("ICD_BACKFILL_LIMIT","100")))
        attempted=0
        for plural,kind in (("diseases","disease"),("symptoms","symptom")):
            for item in mk.list_entities(plural,False,""):
                if attempted >= limit:
                    break
                if medical_taxonomy.approved_mapping(kind,int(item["id"])):
                    continue
                try:
                    medical_taxonomy.queue_entity_candidates(kind,int(item["id"]),3)
                    icd["queued"]+=1; attempted+=1
                except Exception as exc:
                    icd["errors"].append({"kind":kind,"slug":item.get("slug"),"error":type(exc).__name__}); attempted+=1
            if attempted >= limit:
                break
        icd["attempted"]=attempted
        icd["limit"]=limit
    gaps=content_priority.content_gap_report(limit=100)
    print(json.dumps({"symptom_guidance":guidance,"source_gaps":len(source_gaps),"icd11":icd,"content_gaps":gaps[:20]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
