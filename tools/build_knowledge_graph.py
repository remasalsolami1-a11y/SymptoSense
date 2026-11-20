#!/usr/bin/env python3
"""Rebuild knowledge_graph_data.json from the knowledge base (run after editing conditions, symptoms,
blood-test links or medicine groups). The site reads the file; tests fail if it is out of date."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import knowledge_graph  # noqa: E402

if __name__ == "__main__":
    path = knowledge_graph.write_snapshot()
    s = knowledge_graph.snapshot()
    print("wrote", path.name, "-", len(s["nodes"]), "nodes,", len(s["edges"]), "links")
