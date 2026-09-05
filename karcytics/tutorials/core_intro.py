"""Karcytics Core Intro — Active Hands-On Onboarding.

This module defines the ``core_intro_course`` — a Cyto-narrated tutorial that
guides the user through every core Karcytics concept *by actually doing it*, not
just reading about it.

Journey:
  Hub
  ├── 1. Welcome
  ├── 2. Orientation (recent projects + primary actions)
  ├── 3. What is a Project?
  └── 4. [WaitForEvent: PROJECT_LOADED] — user creates their first project
           (spotlight Create New Project)

  Workspace Home Screen
  ├── 5. You're in! Workspace overview
  ├── 6. Header bar (Store + Academy, no spotlight yet)
  ├── 7. The Marketplace explained
  ├── 8. [WaitForEvent: STORE_OPENED] — user opens the Marketplace (spotlight Store button)
  ├── 9. Inside the Marketplace: verified badge & security, in brief
  ├── 10. [WaitForEvent: STORE_MODULE_DETAILS_OPENED] — user views Flow Cytometry details
            (spotlight its card)
  ├── 11. Module details panel explained
  ├── 12. [WaitForEvent: STORE_CLOSED] — user closes the Marketplace
  ├── 13. Module cards & recent sessions, dashboard layout
  └── 14. [WaitForEvent: MODULE_OPENED] — user opens the module (spotlight the Flow Cytometry card)

  Flow Cytometry (handed off — run by that plugin's own local Academy
  engine, see karcytics_plugins.flow_cytometry.tutorials.core_intro_handoff;
  this Hub course just parks at module_phase_wait while it runs)
  ├── Welcome, toolbar, file safety
  ├── Download the demo FCS file (auto-placed in Downloads)
  ├── Import the demo file
  └── Save a workflow

  Back to Home
  ├── 22. Graduation summary — see the workflow card
  └── 23. [BranchingStep] "Let's Start Science! 🔬" → complete + badge

The course is registered on ``module_id = "core"`` — a reserved sentinel.
The ``Course.id`` (``core_intro_v1``) is a stable identifier referenced by
``progress.json`` and several UI call sites — it stays ``v1`` even as the
content evolves, so a version bump here should never rename it.
"""

from karcytics_sdk.plugin.tutorial_models import (
    BranchingStep,
    Course,
    InfoStep,
    InteractionStep,
    WaitForEventStep,
)

# ── Step definitions ──────────────────────────────────────────────────────────

_steps = [
    # ── PHASE 1: Hub ──────────────────────────────────────────────────────────
    InfoStep(
        id="hub_welcome",
        text=(
            "Hey, I'm **Cyto** 👋, your built-in guide to everything Karcytics. Let's have a quick tour!"  # noqa: E501
        ),
        cyto_emotion="cheering",
        cyto_animation="cheering",
        next_step_id="hub_capabilities_intro",
    ),
    InfoStep(
        id="hub_capabilities_intro",
        text=(
            "Karcytics is your powerful, extensible platform for complex data analysis. "
            "It lets you run custom modules locally, completely offline and secure, "
            "and manage all your workflows natively."
        ),
        cyto_emotion="talking",
        next_step_id="hub_open_preferences",
    ),
    WaitForEventStep(
        id="hub_open_preferences",
        text=(
            "First, let's get you set up. Open the **Preferences** dialog from the "
            "menu bar (**Karcytics → Preferences**) so we can customize your workspace."
        ),
        cyto_emotion="pointing",
        event_name="PREFERENCES_OPENED",
        allow_interaction=True,
        next_step_id="hub_about_appearance",
    ),
    InteractionStep(
        id="hub_about_appearance",
        text=(
            "This is the unified Preferences dialog. It starts on the **About** page, "
            "where you can learn about Karcytics. Now, click on **Appearance** in the "
            "left menu to change your theme."
        ),
        cyto_emotion="pointing",
        target_widget_names=["nav_list"],
        target_widget_name="nav_list",
        event_trigger="currentRowChanged",
        allow_interaction=True,
        next_step_id="hub_change_theme",
    ),
    InteractionStep(
        id="hub_change_theme",
        text=(
            "Here you can tweak how Karcytics looks and feels. Try switching your **Theme** "
            "to one you prefer, then click **Privacy & Diagnostics** in the left menu "
            "when you're done."
        ),
        cyto_emotion="happy",
        target_widget_names=["theme_settings_widget", "nav_list"],
        target_widget_name="nav_list",
        event_trigger="currentRowChanged",
        allow_interaction=True,
        next_step_id="hub_preferences_close",
    ),
    WaitForEventStep(
        id="hub_preferences_close",
        text=(
            "This is the **Privacy & Diagnostics** page. The checkbox controls one specific thing: "
            "whether Karcytics **automatically** sends a report if the app crashes hard — "
            "the kind where it shuts down entirely.\n\n"
            "If the box is **unchecked**, nothing is ever sent without your knowledge. "
            "You'll still see the crash dialog and can choose to send manually at any time — "
            "that manual option is always available, regardless of this setting.\n\n"
            "Completely optional — tick the box if you'd like to help, or skip it!\n\n"
            "Whenever you're ready, **close the Preferences dialog** to continue."
        ),
        cyto_emotion="idle",
        target_widget_names=["consent_checkbox"],
        event_name="PREFERENCES_CLOSED",
        allow_interaction=True,
        next_step_id="hub_orientation",
    ),
    InfoStep(
        id="hub_orientation",
        text=(
            "This is the Hub. Your recent projects live on the left — the buttons in the center are how you start **new work**."  # noqa: E501
        ),
        cyto_emotion="talking",
        target_widget_names=["list_recent"],
        next_step_id="hub_what_is_project",
    ),
    InfoStep(
        id="hub_what_is_project",
        text=(
            "Everything you do in Karcytics lives inside a **Project** — its own folder on your machine, holding your data, your workflows, and your results. Keeps things tidy, and keeps datasets from bleeding into each other."  # noqa: E501
        ),
        cyto_emotion="idle",
        next_step_id="hub_create_project_action",
    ),
    WaitForEventStep(
        id="hub_create_project_action",
        text=(
            "Let's make your first one. 👉 Click **✨ Create New Project**, give it a name, and pick a folder."  # noqa: E501
        ),
        cyto_emotion="pointing",
        target_widget_names=["btn_new"],
        event_name="PROJECT_LOADED",
        allow_interaction=True,
        next_step_id="ws_landed",
    ),
    # ── PHASE 2: Workspace Home Screen ────────────────────────────────────────
    InfoStep(
        id="ws_landed",
        text=(
            "🎉 Nice — that's your project. This is the **Workspace**, its command center for everything you do here."  # noqa: E501
        ),
        cyto_emotion="surprised",
        next_step_id="ws_header_bar",
    ),
    InfoStep(
        id="ws_header_bar",
        text=(
            "Up top: **☁️ Store**, where you install new modules, and **🎓 Academy** — actually where I live, along with more tutorials and badges for later. Let's go check out the Store."  # noqa: E501
        ),
        cyto_emotion="talking",
        next_step_id="ws_store_intro",
    ),
    InfoStep(
        id="ws_store_intro",
        text=(
            "Karcytics only ships with the **core app** — you install the tools you actually need. Modules update on their own schedule, so you're never stuck waiting on a big release for one fix."  # noqa: E501
        ),
        cyto_emotion="happy",
        next_step_id="ws_store_open_action",
    ),
    WaitForEventStep(
        id="ws_store_open_action",
        text=("Click **☁️ Store**, top-right, to open the Marketplace."),
        cyto_emotion="pointing",
        target_widget_names=["btn_store"],
        event_name="STORE_OPENED",
        allow_interaction=True,
        next_step_id="ws_store_catalog_explain",
    ),
    InfoStep(
        id="ws_store_catalog_explain",
        text=(
            "Every module here is cryptographically verified by our built-in security checks before it's allowed to run — that's your guarantee it hasn't been tampered with. Updates get the same check, automatically."  # noqa: E501
        ),
        cyto_emotion="talking",
        next_step_id="ws_store_flow_details_action",
    ),
    WaitForEventStep(
        id="ws_store_flow_details_action",
        text=("Find the **Flow Cytometry** card and click **Details** — let's see what it can do."),
        cyto_emotion="pointing",
        target_widget_names=["store_card_flow_cytometry"],
        event_name="STORE_MODULE_DETAILS_OPENED",
        allow_interaction=True,
        next_step_id="ws_store_details_explain",
    ),
    WaitForEventStep(
        id="ws_store_details_explain",
        text=(
            "This panel is the module's full story: what it does, and who built it.\n\n"
            "Take a look around, and when you're done, **close this details panel**."
        ),
        cyto_emotion="talking",
        target_widget_names=["PluginDetailsDialog"],
        event_name="STORE_MODULE_DETAILS_CLOSED",
        allow_interaction=True,
        next_step_id="ws_store_install_action",
    ),
    WaitForEventStep(
        id="ws_store_install_action",
        text=(
            "Grab the **latest version** if you haven't already, "
            "then **close** the Marketplace to head back."
        ),
        cyto_emotion="talking",
        target_widget_names=["store_card_flow_cytometry"],
        event_name="STORE_CLOSED",
        allow_interaction=True,
        next_step_id="ws_layout_top",
    ),
    InfoStep(
        id="ws_layout_top",
        text=(
            "Your **module cards** live up top — each one's a door into its own analysis environment."  # noqa: E501
        ),
        cyto_emotion="talking",
        target_widget_names=["moduleCard"],
        next_step_id="ws_layout_bottom",
    ),
    InfoStep(
        id="ws_layout_bottom",
        text=(
            "Below your module cards, you'll find **Recent Sessions** — empty for now, but once you save a workflow it'll show up right here, one click from where you left off."  # noqa: E501
        ),
        cyto_emotion="talking",
        target_widget_names=["workflows_container"],
        next_step_id="ws_module_card_explain",
    ),
    InfoStep(
        id="ws_module_card_explain",
        text=(
            "**Flow Cytometry** just landed on your dashboard — that's what installing it a moment ago got you."  # noqa: E501
        ),
        cyto_emotion="talking",
        next_step_id="ws_open_module_action",
    ),
    WaitForEventStep(
        id="ws_open_module_action",
        text=("Click the **Flow Cytometry** card to open it up."),
        cyto_emotion="pointing",
        target_widget_names=["module_card_flow_cytometry"],
        event_name="MODULE_OPENED",
        allow_interaction=True,
        next_step_id="module_phase_wait",
    ),
    # ── PHASE 3: Analysis Panel ───────────────────────────────────────────────
    # Flow Cytometry now runs as a genuinely separate OS process (the V3
    # isolated engine) — the Hub can no longer findChild() its buttons or
    # connect to their signals, so this phase's steps (welcome, data
    # integrity, import the demo file, save the workflow) are no longer
    # defined here. They live in karcytics_plugins.flow_cytometry.tutorials
    # .core_intro_handoff, run by that plugin's own local Academy engine —
    # the same mechanism its course1_fundamentals uses to spotlight its own
    # real widgets from inside its own process. This step just parks the
    # Hub's tour while that runs; plugin_loader.py's
    # _instantiate_isolated_overlay is what actually starts the handoff
    # course (staged via daemon.pending_academy_handoff, right as this step
    # becomes current), and karcytics.core.plugins.loader's
    # _wire_academy_handoff_forwarding is what jumps this tour straight to
    # analysis_saved_confirm_spotlight once that course reports back done —
    # this step's own next_step_id below is never actually reached through
    # the normal Next-button path, only kept so the step is never left in a
    # dangling state.
    InfoStep(
        id="module_phase_wait",
        text=(
            "🧬 Head into **Flow Cytometry** — I'll meet you there to walk through importing data and saving your first workflow. Click next here once done."  # noqa: E501
        ),
        cyto_emotion="pointing",
        allow_interaction=True,
        next_step_id="analysis_saved_confirm_spotlight",
    ),
    InfoStep(
        id="analysis_saved_confirm_spotlight",
        text=(
            "There it is — the workflow you just built, sitting under **Recent Sessions**. One click and you're back in it."  # noqa: E501
        ),
        cyto_emotion="happy",
        target_widget_names=["workflows_container"],
        allow_scroll=True,
        next_step_id="cleanup_explain",
    ),
    # ── PHASE 4: Graduation ───────────────────────────────────────────────────
    InfoStep(
        id="cleanup_explain",
        text=(
            "Quick housekeeping: the **⚙️ gear** on a session card renames or deletes it. To remove a whole project, right-click it back in the Hub's recent list."  # noqa: E501
        ),
        cyto_emotion="talking",
        next_step_id="restart_reminder",
    ),
    InfoStep(
        id="restart_reminder",
        text=(
            "One last thing: if you ever need a refresher, you can always take "
            "this tour again by selecting **Help → Restart Onboarding Tour** from "
            "the top menu."
        ),
        cyto_emotion="happy",
        next_step_id="graduation",
    ),
    InfoStep(
        id="graduation",
        text=(
            "🏆 That's the tour! You've made a **project**, installed a **module**, imported **real data**, and **saved your work**."  # noqa: E501
        ),
        cyto_emotion="cheering",
        cyto_animation="cheering",
        next_step_id="finish",
    ),
    BranchingStep(
        id="finish",
        text=("You've earned the **🧭 Karcytics Explorer** badge. Go make something."),
        cyto_emotion="happy",
        options={
            "Let's Start Science! 🔬": "__complete__",
        },
    ),
]

# ── Course object ─────────────────────────────────────────────────────────────

core_intro_course = Course(
    id="core_intro_v1",
    title="Karcytics Onboarding Tour",
    description=(
        "A hands-on walkthrough where you create a real project, explore the "
        "Marketplace, open the Flow Cytometry module, import data, and save "
        "your first workflow."
    ),
    estimated_minutes=10,
    badge_reward="Karcytics Explorer",
    badge_icon="🧭",
    prerequisite_course_ids=[],
    steps=_steps,
)
