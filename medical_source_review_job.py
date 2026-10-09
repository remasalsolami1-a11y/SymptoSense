"""CLI helper: fetch official source candidates into the manual review queue."""
import argparse, json
import medical_source_pipeline as pipeline

p=argparse.ArgumentParser()
p.add_argument("term")
p.add_argument("--lang", choices=["ar","en"], default="ar")
p.add_argument("--nhs-section", default=None)
p.add_argument("--nhs-slug", default=None)
a=p.parse_args()
print(json.dumps(pipeline.queue_research_bundle(a.term,a.lang,a.nhs_section,a.nhs_slug), ensure_ascii=False, indent=2))
