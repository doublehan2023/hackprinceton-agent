from typing import Dict


def generate_redlines(clauses: Dict):
    """
    Converts analyzed clauses into structured legal redlines
    """

    redlines = []

    for name, data in clauses.items():

        original = data.get("text", "")
        deviation = data.get("deviation", "minor")
        suggestion = data.get("suggestion", "No suggestion provided")
        detail = data.get("detail", "")

        # -----------------------------
        # Severity styling
        # -----------------------------
        if deviation == "critical":
            action = "MUST REPLACE"
            severity_color = "red"
        elif deviation == "minor":
            action = "REVISE"
            severity_color = "orange"
        else:
            action = "ACCEPTABLE"
            severity_color = "green"

        # -----------------------------
        # Build redline object
        # -----------------------------
        redlines.append({
            "clause": name,

            "severity": deviation,

            "action": action,

            "original_text": original,

            "suggested_text": suggestion if suggestion else original,

            "diff": {
                "removed": original,
                "added": suggestion
            },

            "reason": detail,

            "ui_style": {
                "color": severity_color
            }
        })

    return redlines