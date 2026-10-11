"""The Settings tab: add, edit and remove categories."""

import pandas as pd
import psycopg
import streamlit as st

from chase_import.category_list import (
    CategoryFileError, plan_changes, read_file, template, to_excel_bytes, to_sheet,
)
from chase_import.dashboard.data import (
    add_category, apply_category_list, category_usage, load_category_table, remove_category,
    update_categories,
)
from chase_import.dashboard.notify import rerun_with

# The view falls back to this name for anything nobody has categorized,
# so it must always exist under exactly this name.
PROTECTED = "Uncategorized"
NEW_GROUP = "➕ New group..."
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def done(message: str) -> None:
    """Start the page over so every tab sees the change, with `message` as a pop-up."""
    rerun_with(message)


# ---------------------------------------------------------------- edit


def problems_with(edited: pd.DataFrame) -> list[str]:
    """Reasons the edited table can't be saved. Empty list = fine."""
    problems = []
    names = edited["subcategory"].fillna("").str.strip()
    groups = edited["category"].fillna("").str.strip()
    if (names == "").any() or (groups == "").any():
        problems.append("Every row needs a subcategory and a group.")
    if names.str.lower().duplicated().any():
        problems.append("Two subcategories can't have the same name.")
    if PROTECTED in edited.index and names[PROTECTED] != PROTECTED:
        problems.append(f"'{PROTECTED}' can't be renamed: it's what uncategorized "
                        "transactions fall back to.")
    return problems


def edit_card(cats: pd.DataFrame) -> None:
    """Every subcategory in one editable table."""
    with st.container(key="card-settings-edit"):
        st.subheader("Your categories")
        st.caption("Change a name, group or checkbox, then press Save. Renaming a "
                   "subcategory keeps all its rules, fixes and AI answers.")

        # The original name becomes the hidden index, so a renamed row still
        # knows which database row it came from.
        table = cats.set_index(cats["subcategory"].rename("original"))

        edited = st.data_editor(
            table,
            hide_index=True,
            column_config={
                "subcategory": st.column_config.TextColumn("Subcategory", required=True),
                "category": st.column_config.TextColumn("Group", required=True),
                "is_spending": st.column_config.CheckboxColumn(
                    "Counts as spending", help="Off for income, transfers and card payments"
                ),
                "tax_relevant": st.column_config.CheckboxColumn("Tax-relevant"),
            },
            key=f"settings-edit-{hash(tuple(map(tuple, table.values)))}",
        )

        changed = (edited != table).any(axis=1)
        count = int(changed.sum())
        if not st.button(f"Save {count} change(s)", type="primary", disabled=count == 0,
                         key="settings-save"):
            return

        problems = problems_with(edited)
        if problems:
            for problem in problems:
                st.error(problem)
            return

        rows = [
            (old, r.subcategory.strip(), r.category.strip(), bool(r.is_spending), bool(r.tax_relevant))
            for old, r in edited[changed].iterrows()
        ]
        try:
            update_categories(rows)
        except psycopg.errors.UniqueViolation:
            st.error("That name is already taken by another subcategory.")
            return
        done(f"Saved {count} change(s).")


# ---------------------------------------------------------------- add


def add_card(cats: pd.DataFrame) -> None:
    """Add one subcategory, in an existing group or a new one."""
    with st.container(key="card-settings-add"):
        st.subheader("Add a subcategory")

        col_name, col_group = st.columns(2)
        name = col_name.text_input("Name", key="add-name", placeholder="e.g. Grandkids").strip()
        groups = sorted(cats["category"].unique())
        group = col_group.selectbox("Group", groups + [NEW_GROUP], key="add-group")
        if group == NEW_GROUP:
            group = col_group.text_input("New group name", key="add-new-group").strip()

        is_spending = st.checkbox("Counts as spending", value=True, key="add-spending",
                                  help="Turn off for income, transfers and card payments.")
        tax_relevant = st.checkbox("Tax-relevant", key="add-tax")

        if not st.button("Add", disabled=not (name and group), key="add-button"):
            return
        if name.lower() in cats["subcategory"].str.lower().values:
            st.error(f"'{name}' already exists.")
            return

        add_category(name, group, is_spending, tax_relevant)
        # Empty the boxes for next time. Widget values live in session_state
        # under their keys; deleting them before the rerun resets the widgets.
        for key in ("add-name", "add-new-group", "add-group", "add-spending", "add-tax"):
            st.session_state.pop(key, None)
        done(f"Added '{name}' to {group}.")


# ---------------------------------------------------------------- spreadsheet


def file_card(cats: pd.DataFrame, show_export: bool = True) -> None:
    """Download your list or a template; upload a list to add or update many at once.

    show_export=False hides "Download my categories" (the welcome page has nothing to export yet).
    """
    with st.container(key="card-settings-file"):
        st.subheader("Import or export a category list")
        st.caption("Edit your categories in Excel, or start from someone else's list. "
                   "Uploading adds new subcategories and updates changed ones. It never "
                   "removes anything (that's the Remove card on Settings).")

        col_template, col_mine = st.columns(2)
        col_template.download_button(
            "Download a blank template", data=to_excel_bytes(template()),
            file_name="category_template.xlsx", mime=XLSX, key="cat-template",
        )
        if show_export:
            col_mine.download_button(
                "Download my categories", data=to_excel_bytes(to_sheet(cats)),
                file_name="my_categories.xlsx", mime=XLSX, key="cat-export",
            )

        # Bumping this number after Apply gives a fresh, empty uploader
        # (a file uploader can't be emptied directly).
        round_ = st.session_state.get("cat_file_round", 0)
        upload = st.file_uploader("Upload a category list (.xlsx or .csv)",
                                  type=["xlsx", "csv"], key=f"cat-file-{round_}")
        if upload is None:
            return

        try:
            plan = plan_changes(read_file(upload.name, upload.getvalue()), cats)
        except CategoryFileError as e:
            st.error(str(e))
            return
        except Exception as e:  # a damaged or password-protected file, say
            st.error(f"Couldn't read {upload.name}: {e}")
            return

        st.markdown(f"**{len(plan.new)}** new · **{len(plan.changed)}** changed · "
                    f"**{plan.unchanged}** already the same · **{len(plan.problems)}** skipped")
        if plan.problems:
            st.warning("These rows will be skipped:\n\n"
                       + "\n".join(f"- {problem}" for problem in plan.problems))
        if not plan.to_apply:
            st.info("Nothing to change: your categories already match this file.")
            return

        preview = pd.DataFrame(
            [("New", *row) for row in plan.new] + [("Update", *row) for row in plan.changed],
            columns=["Change", "Subcategory", "Group", "Counts as spending", "Tax-relevant"],
        )
        st.dataframe(preview, hide_index=True)

        if not st.button(f"Apply {len(plan.to_apply)} change(s)", type="primary",
                         key="cat-file-apply"):
            return
        apply_category_list(plan.to_apply)
        st.session_state["cat_file_round"] = round_ + 1
        done(f"Added {len(plan.new)} and updated {len(plan.changed)} subcategories.")


# ---------------------------------------------------------------- remove


def remove_card(cats: pd.DataFrame) -> None:
    """Remove a subcategory, moving everything that used it somewhere else."""
    with st.container(key="card-settings-remove"):
        st.subheader("Remove a subcategory")

        removable = [s for s in cats["subcategory"] if s != PROTECTED]
        target = st.selectbox("Remove", removable, index=None,
                              placeholder="Pick a subcategory", key="remove-target")
        if target is None:
            return

        used = category_usage(target)
        st.caption(
            f"'{target}' is on {used['transactions']:,} transaction(s), through "
            f"{used['rules']} rule(s), {used['fixes']} fix(es) by hand and "
            f"{used['ai']} AI answer(s). Those will move to the subcategory you pick. "
            f"Picking '{PROTECTED}' forgets them instead, so you can sort those "
            "transactions out again on the Review tab."
        )

        others = [s for s in cats["subcategory"] if s != target]
        # Both keys include the target, so picking a different subcategory starts
        # these fresh: a tick meant for one subcategory never carries over to another.
        replacement = st.selectbox("Move them to", others, index=others.index(PROTECTED),
                                   key=f"remove-replacement-{target}")

        sure = st.checkbox(f"Yes, remove '{target}' and move everything to '{replacement}'",
                           key=f"remove-sure-{target}")
        if not st.button(f"Remove {target}", type="primary", disabled=not sure,
                         key="remove-button"):
            return

        remove_category(target, replacement)
        for key in ("remove-target", f"remove-replacement-{target}", f"remove-sure-{target}"):
            st.session_state.pop(key, None)
        done(f"Removed '{target}'. Everything it had now goes to '{replacement}'.")


# ---------------------------------------------------------------- the tab


def settings_tab() -> None:
    """Edit, add and remove categories."""
    cats = load_category_table()
    edit_card(cats)
    file_card(cats)
    add_card(cats)
    remove_card(cats)
