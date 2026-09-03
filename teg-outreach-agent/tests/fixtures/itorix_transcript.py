"""Itorix Infotech LLP — regression fixture for discovery v2.

This is the real conversation from the DB (Tushar Mandale / Itorix Infotech
LLP) plus the ``TurnSignals`` an ideal extraction *should* produce for each
prospect turn. The regression test replays these and asserts:

  * after the "7 facts" turn the system does NOT offer a proposal
  * discovery keeps going, into what they sell / how they acquire clients / why
    Gujarat specifically
  * "manufacturing and e-commerce" stays prospect-stated, verbatim, and is
    never replaced by a research-inferred industry set
  * growth_posture is "market_test", never inferred as expansion
  * a brief validation playback happens before the proposal transition

Itorix is a *fixture*. No Itorix-specific logic lives in the code.
"""
from app.domain.discovery import IncomingSignal, TurnSignals


def _f(**pairs) -> dict[str, IncomingSignal]:
    out: dict[str, IncomingSignal] = {}
    for k, v in pairs.items():
        if isinstance(v, tuple):
            value, ev, vb = (v + (None,))[:3]
            out[k] = IncomingSignal(value=value, evidence=ev, verbatim=vb)
        else:
            out[k] = IncomingSignal(value=v, evidence="prospect_stated", verbatim=v)
    return out


# Each entry: (prospect_message, ideal_turn_signals, model_wants_proposal)
ITORIX_TURNS: list[tuple[str, TurnSignals, bool]] = [
    (
        "Honestly, we've never exhibited at an out-of-state expo before, so we are "
        "just trying to figure out if it actually makes sense for a Pune-based "
        "agency like ours. Our primary goal is strictly new client acquisition, "
        "specifically finding 3 to 5 qualified enterprise clients from the "
        "manufacturing or e-commerce sectors who have real budgets for digital "
        "transformation.",
        TurnSignals(
            fields=_f(
                objective=("new client acquisition", "prospect_stated",
                           "primary goal is strictly new client acquisition"),
                objective_type=("sales", "inference"),
                desired_outcome=("3-5 qualified enterprise clients", "prospect_stated",
                                 "finding 3 to 5 qualified enterprise clients"),
                target_industries=("manufacturing, e-commerce", "prospect_stated",
                                   "manufacturing or e-commerce sectors"),
                target_company_type=("enterprise firms with real digital-transformation budgets",
                                     "prospect_stated", "real budgets for digital transformation"),
                target_geography=("Gujarat", "inference"),
                event_experience=("first out-of-state expo", "prospect_stated",
                                  "never exhibited at an out-of-state expo before"),
                growth_posture=("market_test", "prospect_stated",
                                "just trying to figure out if it actually makes sense"),
            ),
        ),
        False,
    ),
    (
        "Since we are totally new to this and it's a big trip from Pune, we would "
        "start very small. It would likely just be a lean team of 2 or 3 people, "
        "including myself and one of our core technical leads, to handle the "
        "strategy conversations.",
        TurnSignals(
            fields=_f(
                team_attending=("2-3", "prospect_stated", "a lean team of 2 or 3 people"),
                attendee_roles=("founder plus a core technical lead", "prospect_stated",
                                "including myself and one of our core technical leads"),
                readiness_concerns=("big trip from Pune; totally new to this",
                                    "prospect_stated", "it's a big trip from Pune"),
                setup_need=("small / entry-level", "inference"),
            ),
        ),
        False,
    ),
    (
        "Yes, that would be very helpful. Please put that proposal together and "
        "include the exact pricing structures for the simpler, entry-level layouts "
        "you recommend for a small team of our size.",
        TurnSignals(
            fields=_f(
                setup_need=("simpler entry-level layout for a small team", "prospect_stated",
                            "the simpler, entry-level layouts ... for a small team of our size"),
            ),
            intents=["requested_proposal"],
            asked_about_price=True,
        ),
        True,
    ),
    # --- turns the NEW system should still have, that the old one skipped ---
    (
        "The work we'd really want to win is end-to-end digital transformation — "
        "commerce platforms and the systems around them — not one-off websites. "
        "Right now most of our enterprise work comes through referrals and a bit "
        "of outbound; we have almost no direct route into Gujarat.",
        TurnSignals(
            fields=_f(
                what_they_sell=("end-to-end digital transformation: commerce platforms "
                                "and surrounding systems", "prospect_stated",
                                "end-to-end digital transformation — commerce platforms "
                                "and the systems around them"),
                high_value_offering=("end-to-end digital-transformation engagements",
                                     "prospect_stated", "the work we'd really want to win"),
                acquisition_channels=("referrals and some outbound", "prospect_stated",
                                      "comes through referrals and a bit of outbound"),
                acquisition_constraints=("almost no direct route into Gujarat",
                                         "prospect_stated",
                                         "we have almost no direct route into Gujarat"),
            ),
        ),
        False,
    ),
    (
        "The person we need to get in front of is usually the ops or digital "
        "transformation head — sometimes a CTO at the larger firms.",
        TurnSignals(
            fields=_f(
                target_buyer_role=("operations / digital transformation head, sometimes CTO",
                                   "prospect_stated",
                                   "the ops or digital transformation head — sometimes a CTO"),
            ),
        ),
        False,
    ),
    # --- prospect confirms the playback ---
    (
        "Yes, that's exactly right.",
        TurnSignals(intents=["confirmed_understanding"]),
        False,
    ),
]
