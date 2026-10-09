"""Admin knowledge-base management API routes (categories, diseases,
symptoms, sources, relationships, red flags).

Extracted from webapp.py as a first, verified step of splitting the large
monolithic route file into smaller modules. This module does not import
webapp.py (avoiding a circular import); webapp.py instead calls
``register(...)`` once at startup, passing its own existing helpers. Route
paths, decorators, and logic are unchanged from the original inline version.
"""
from flask import request, jsonify

import clinical_review
import medical_knowledge


def register(app, admin_api_required, _mk_error, _admin_allowed, _admin_role, _ss_user):
    """Attach every admin knowledge-base route to ``app``. Called once from
    webapp.py during startup, in the same place these routes used to be
    defined inline."""

    def _queue_for_review(kind, entity_id=None):
        """Publishing changes go to the clinical review queue (see clinical_review.py)."""
        if not clinical_review.required():
            return None
        row = clinical_review.submit(kind, request.get_json(silent=True) or {}, _ss_user(), entity_id)
        return jsonify({"ok": True, "pending_review": row, "published": False}), 202

    @app.route("/api/admin/knowledge/bootstrap", methods=["GET"])
    @admin_api_required("access")
    def api_admin_knowledge_bootstrap():
        try:
            include = _admin_allowed("medical")
            return jsonify({
                "ok": True,
                "role": _admin_role(),
                "can_edit": include,
                # Analytics admins receive aggregate statistics only.  Medical
                # content rows are available only to the two editing roles.
                "categories": medical_knowledge.categories() if include else [],
                "diseases": medical_knowledge.list_entities("diseases", True) if include else [],
                "symptoms": medical_knowledge.list_entities("symptoms", True) if include else [],
                "sources": medical_knowledge.list_entities("sources", True) if include else [],
                "relationships": medical_knowledge.list_relationships() if include else [],
                "red_flags": medical_knowledge.list_entities("red_flags", True) if include else [],
                "statistics": medical_knowledge.statistics(),
            })
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/knowledge/stats", methods=["GET"])
    @admin_api_required("analytics")
    def api_admin_knowledge_stats():
        return jsonify({"ok": True, "statistics": medical_knowledge.statistics()})


    @app.route("/api/admin/knowledge/review-status", methods=["GET"])
    @admin_api_required("medical")
    def api_admin_knowledge_review_status():
        try:
            try:
                days=max(30,min(1095,int(request.args.get("days") or 365)))
                red_days=max(30,min(days,int(request.args.get("red_flag_days") or 180)))
            except (TypeError, ValueError):
                days, red_days = 365, 180
            return jsonify({"ok":True,"review":medical_knowledge.periodic_review_status(days,red_days)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/knowledge/unmatched-symptoms", methods=["GET"])
    @admin_api_required("analytics")
    def api_admin_unmatched_symptoms():
        try:
            days = min(max(int(request.args.get("days", 30)), 1), 365)
            limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        except (TypeError, ValueError):
            days, limit = 30, 50
        return jsonify({
            "ok": True,
            "days": days,
            "unmatched": medical_knowledge.unmatched_symptom_report(limit=limit, days=days),
        })


    @app.route("/api/admin/categories", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_categories():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "categories": medical_knowledge.categories(request.args.get("q", ""), True)})
            return jsonify({"ok": True, "category": medical_knowledge.save_category(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/categories/<int:entity_id>", methods=["PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_category(entity_id):
        try:
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_category(entity_id, _ss_user())})
            return jsonify({"ok": True, "category": medical_knowledge.save_category(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/diseases", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_diseases():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "diseases": medical_knowledge.list_entities("diseases", True, request.args.get("q", ""), request.args.get("category"), request.args.get("severity"))})
            queued = _queue_for_review("disease")
            if queued is not None:
                return queued
            return jsonify({"ok": True, "disease": medical_knowledge.save_disease(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/diseases/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_disease(entity_id):
        try:
            if request.method == "GET":
                item = medical_knowledge.get_entity("disease", entity_id)
                return jsonify({"ok": bool(item), "disease": item}) if item else _mk_error("not_found", 404)
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_entity("disease", entity_id, _ss_user())})
            queued = _queue_for_review("disease", entity_id)
            if queued is not None:
                return queued
            return jsonify({"ok": True, "disease": medical_knowledge.save_disease(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/symptoms", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_symptoms():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "symptoms": medical_knowledge.list_entities("symptoms", True, request.args.get("q", ""), request.args.get("category"))})
            queued = _queue_for_review("symptom")
            if queued is not None:
                return queued
            return jsonify({"ok": True, "symptom": medical_knowledge.save_symptom(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/symptoms/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_symptom(entity_id):
        try:
            if request.method == "GET":
                item = medical_knowledge.get_entity("symptom", entity_id)
                return jsonify({"ok": bool(item), "symptom": item}) if item else _mk_error("not_found", 404)
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_entity("symptom", entity_id, _ss_user())})
            queued = _queue_for_review("symptom", entity_id)
            if queued is not None:
                return queued
            return jsonify({"ok": True, "symptom": medical_knowledge.save_symptom(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/sources", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_sources():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "sources": medical_knowledge.list_entities("sources", True, request.args.get("q", ""), verification=request.args.get("verification"))})
            return jsonify({"ok": True, "source": medical_knowledge.save_source(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/sources/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_source(entity_id):
        try:
            if request.method == "GET":
                item = medical_knowledge.get_entity("source", entity_id)
                return jsonify({"ok": bool(item), "source": item}) if item else _mk_error("not_found", 404)
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_entity("source", entity_id, _ss_user())})
            return jsonify({"ok": True, "source": medical_knowledge.save_source(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/relationships", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_relationships():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "relationships": medical_knowledge.list_relationships(request.args.get("q", ""))})
            return jsonify({"ok": True, "relationship": medical_knowledge.save_relationship(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/relationships/<int:entity_id>", methods=["PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_relationship(entity_id):
        try:
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_entity("relationship", entity_id, _ss_user())})
            return jsonify({"ok": True, "relationship": medical_knowledge.save_relationship(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/red-flags", methods=["GET", "POST"])
    @admin_api_required("medical")
    def api_admin_red_flags():
        try:
            if request.method == "GET":
                return jsonify({"ok": True, "red_flags": medical_knowledge.list_entities("red_flags", True, request.args.get("q", ""))})
            queued = _queue_for_review("red_flag")
            if queued is not None:
                return queued
            return jsonify({"ok": True, "red_flag": medical_knowledge.save_red_flag(request.get_json(silent=True) or {}, _ss_user())}), 201
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/red-flags/<int:entity_id>", methods=["GET", "PUT", "DELETE"])
    @admin_api_required("medical")
    def api_admin_red_flag(entity_id):
        try:
            if request.method == "GET":
                item = medical_knowledge.get_entity("red_flag", entity_id)
                return jsonify({"ok": bool(item), "red_flag": item}) if item else _mk_error("not_found", 404)
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_entity("red_flag", entity_id, _ss_user())})
            queued = _queue_for_review("red_flag", entity_id)
            if queued is not None:
                return queued
            return jsonify({"ok": True, "red_flag": medical_knowledge.save_red_flag(request.get_json(silent=True) or {}, _ss_user(), entity_id)})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/<kind>/<int:entity_id>/sources", methods=["POST", "DELETE"])
    @admin_api_required("medical")
    def api_admin_source_link(kind, entity_id):
        if kind not in {"diseases", "symptoms"}:
            return _mk_error("invalid_entity", 404)
        singular = "disease" if kind == "diseases" else "symptom"
        try:
            data = request.get_json(silent=True) or {}
            if request.method == "DELETE":
                return jsonify({"ok": medical_knowledge.delete_source_link(singular, entity_id, int(data.get("source_id")), _ss_user())})
            return jsonify({"ok": True, "link": medical_knowledge.save_source_link(singular, entity_id, data, _ss_user())})
        except Exception as exc:
            return _mk_error(exc)


    @app.route("/api/admin/knowledge/audit", methods=["GET"])
    @admin_api_required("medical")
    def api_admin_knowledge_audit():
        return jsonify({"ok": True, "audit": medical_knowledge.audit_log(request.args.get("limit", 100))})


    @app.route("/api/admin/knowledge/versions/<entity_type>/<int:entity_id>", methods=["GET"])
    @admin_api_required("medical")
    def api_admin_knowledge_versions(entity_type, entity_id):
        return jsonify({"ok": True, "versions": medical_knowledge.versions(entity_type, entity_id)})


    @app.route("/api/admin/clinical-reviews", methods=["GET"])
    @admin_api_required("medical")
    def api_admin_clinical_reviews():
        status = request.args.get("status", "pending")
        return jsonify({"ok": True, "reviews": clinical_review.list_reviews(None if status == "all" else status), "counts": clinical_review.counts()})


    @app.route("/api/admin/clinical-reviews/<int:review_id>/<action>", methods=["POST"])
    @admin_api_required("medical")
    def api_admin_clinical_review_decide(review_id, action):
        if action not in {"approve", "reject"}:
            return _mk_error("invalid_action", 404)
        try:
            note = (request.get_json(silent=True) or {}).get("note", "")
            return jsonify({"ok": True, "review": clinical_review.decide(review_id, action == "approve", _ss_user(), note)})
        except ValueError as exc:
            # Workflow rule violations are safe, fixed codes (not_found, already_decided, self_review_not_allowed, ...).
            code = str(exc)
            return jsonify({"ok": False, "error": code}), (404 if code == "not_found" else 409 if code == "already_decided" else 400)
        except Exception as exc:
            return _mk_error(exc)
