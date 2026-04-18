from backend.schemas import ClauseType


ACTA_PLAYBOOK: dict[ClauseType, dict[str, object]] = {
    ClauseType.confidentiality: {
        "standard_text": (
            "Confidential information must remain protected for five years, excluding information "
            "that is publicly known, independently developed, or rightfully received from a third party."
        ),
        "required_terms": ["five years", "publicly known", "independently developed"],
    },
    ClauseType.indemnification: {
        "standard_text": (
            "Indemnification should be mutual and negligence-based only. The sponsor indemnifies "
            "for product liability, and neither party gives blanket indemnification."
        ),
        "required_terms": ["mutual", "negligence", "product liability"],
    },
    ClauseType.payment_terms: {
        "standard_text": (
            "Invoices are paid net 30 and follow an itemized budget with indirect costs capped at 26% F&A."
        ),
        "required_terms": ["net 30", "itemized budget", "26%"],
    },
    ClauseType.intellectual_property: {
        "standard_text": (
            "The sponsor retains rights to the investigational compound and derivatives, while the site "
            "retains rights to independently developed intellectual property."
        ),
        "required_terms": ["sponsor retains", "derivatives", "independently developed"],
    },
    ClauseType.publication_rights: {
        "standard_text": (
            "The site receives a 60-day review period before publication. The sponsor may delay publication "
            "for up to 90 days only to permit patent filing."
        ),
        "required_terms": ["60-day", "90 days", "patent"],
    },
    ClauseType.termination: {
        "standard_text": (
            "Termination rights should identify notice requirements, patient safety protections, and "
            "post-termination obligations for data, close-out, and payment."
        ),
        "required_terms": ["notice", "patient safety", "close-out"],
    },
    ClauseType.governing_law: {
        "standard_text": (
            "Governing law and venue should be commercially reasonable and avoid one-sided litigation burdens."
        ),
        "required_terms": ["governing law", "venue"],
    },
    ClauseType.subject_injury: {
        "standard_text": (
            "The sponsor covers research-related injury costs. The site remains responsible only for "
            "standard-of-care obligations that are not caused by the investigational product or protocol."
        ),
        "required_terms": ["research-related injury", "standard of care"],
    },
    ClauseType.protocol_deviations: {
        "standard_text": (
            "Protocol deviations must be reported to the sponsor within five business days."
        ),
        "required_terms": ["five business days", "reported to the sponsor"],
    },
    ClauseType.general: {
        "standard_text": "Review this clause against the closest ACTA baseline section and escalate uncertainty.",
        "required_terms": [],
    },
}


CORE_CLAUSE_TYPES = [
    ClauseType.confidentiality,
    ClauseType.indemnification,
    ClauseType.payment_terms,
    ClauseType.intellectual_property,
    ClauseType.publication_rights,
    ClauseType.termination,
    ClauseType.governing_law,
]
