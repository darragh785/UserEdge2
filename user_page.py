from typing import Dict, List, Optional, Callable

from nicegui import ui
from db_connector_pg import PostgresConnector


def _csv_to_roles(text: Optional[str]) -> List[str]:
    return [r.strip() for r in (text or "").split(",") if r.strip()]


class UsersPage:
    def __init__(self, repo: PostgresConnector, on_view_devices: Callable[[str], None]):
        self.repo = repo
        self.on_view_devices = on_view_devices

        ui.page_title("Users Admin")

        # Header bar
        with ui.row().classes(
            "bg-cyan-600 text-white items-center px-3 py-2 rounded w-full"
        ):
            # https://tailwindcss.com/docs/colors
            ui.label("Users Admin").classes("text-xl font-semibold")
            ui.space()

        # Search box
        search = ui.input("Search")

        # Table with single selection (no slots needed)
        self.table = ui.table(
            columns=[
                {"name": "id", "label": "UUID", "field": "id"},
                {
                    "name": "username",
                    "label": "Username",
                    "field": "username",
                    "sortable": True,
                },
                {
                    "name": "roles",
                    "label": "Roles",
                    "field": "roles",
                    "sortable": True,
                },
                {
                    "name": "devices",
                    "label": "Devices",
                    "field": "devices",
                    "sortable": True,
                },
                {
                    "name": "updated_at",
                    "label": "Updated",
                    "field": "updated_at",
                    "sortable": True,
                },
                {
                    "name": "deleted_at",
                    "label": "Deleted",
                    "field": "deleted_at",
                    "sortable": True,
                },
            ],
            rows=[],
            row_key="id",
        ).classes("w-full mt-2").props('selection="single"')

        self.table.on("selection", self.update_buttons)
        search.bind_value(self.table, "filter")

        # Buttons row
        with ui.row().classes("gap-2 my-2"):
            self.btn_add = ui.button("Add user", on_click=self.open_add_dialog)

            self.btn_edit = ui.button("Edit", on_click=self.open_edit_dialog)
            self.btn_edit.disable()

            self.btn_del = ui.button(
                "Delete", on_click=self.open_delete_dialog
            ).props("color=negative")
            self.btn_del.disable()

            self.btn_harddel = ui.button(
                "Hard-delete", on_click=self.open_hard_delete_dialog
            ).props("color=negative")
            self.btn_harddel.visible = False

            self.btn_viewdev = ui.button(
                "View devices", on_click=self._view_devices_for_selected
            )
            self.btn_viewdev.disable()

        self.refresh()

    # ---- data + state ----
    def refresh(self) -> None:
        users = self.repo.get_all_users()
        counts = self.repo.get_user_device_counts()
        rows: List[Dict] = []

        for u in users:
            r = u.to_ui_row()
            # r['id'] is string UUID
            r["devices"] = counts.get(r["id"], 0)
            rows.append(r)

        self.table.rows = rows
        self.table.update()

        if hasattr(self.table, "selected"):
            self.table.selected = []

        self.update_buttons()

    def selected_row(self) -> Optional[Dict]:
        sel = getattr(self.table, "selected", [])
        return sel[0] if sel else None

    def update_buttons(self, e=None) -> None:
        self.btn_edit.disable()
        self.btn_del.disable()
        self.btn_viewdev.disable()

        self.btn_del.text = "Delete"
        self.btn_harddel.visible = False

        if bool(getattr(self.table, "selected", [])):
            self.btn_edit.enable()
            self.btn_del.enable()
            self.btn_viewdev.enable()

            if self.selected_row().get("deleted_at"):
                self.btn_del.text = "Undelete"
                self.btn_harddel.visible = True

        self.btn_edit.update()
        self.btn_del.update()
        self.btn_viewdev.update()

    def _view_devices_for_selected(self) -> None:
        sel = getattr(self.table, "selected", [])
        if not sel:
            ui.notify("Select a user first", type="warning")
            return
        # Pass the selected user's id (string UUID) to the callback
        self.on_view_devices(str(sel[0]["id"]))

    def set_show_uuid(self, show: bool) -> None:
        """Show/hide the UUID column."""
        col_names = [c["name"] for c in self.table.columns]
        visible = col_names if show else [n for n in col_names if n != "id"]
        self.table.props(f'visible-columns={",".join(visible)}')
        self.table.update()

    # ---- dialogs (from basic version) ----
    def open_add_dialog(self) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
            ui.label("Add user").classes("text-lg")

            name = ui.input("Username").classes("w-full")
            pw = ui.input("Password").props("type=password").classes("w-full")
            roles = ui.input("Roles (comma-separated)").classes("w-full")

            with ui.row().classes("justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close)

                def save() -> None:
                    if not name.value or not pw.value:
                        ui.notify(
                            "Username and password required", type="warning"
                        )
                        return
                    try:
                        self.repo.create_user(
                            name.value,
                            pw.value,
                            _csv_to_roles(roles.value),
                        )
                        ui.notify("User created")
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f"DB error: {e}", type="negative")

                ui.button("Save", on_click=save).props("color=primary")

        dialog.open()

    def open_hard_delete_dialog(self) -> None:
        sel = self.selected_row()
        deleted = True if sel and sel.get("deleted_at") else False
        if not sel or not deleted:
            ui.notify("Select a soft deleted row first", type="warning")
            return

        with ui.dialog() as dialog, ui.card():
            ui.label(
                f'Hard delete (irreversible) user "{sel["username"]}"?'
            ).classes("text-lg")

            with ui.row().classes("justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close)

                def delete() -> None:
                    try:
                        self.repo.hard_delete_user(sel["id"])
                        ui.notify("User hard-deleted")  # permanently gone
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f"DB error: {e}", type="negative")

                ui.button(
                    "Hard Delete", on_click=delete
                ).props("color=negative")

        dialog.open()

    def open_edit_dialog(self) -> None:
        sel = self.selected_row()
        if not sel:
            ui.notify("Select a row first", type="warning")
            return

        with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
            ui.label(f'Edit user: {sel["username"]}').classes("text-lg")

            name = ui.input("Username", value=sel["username"]).classes(
                "w-full"
            )
            roles = ui.input(
                "Roles (comma-separated)", value=sel.get("roles") or ""
            ).classes("w-full")
            new_pw = ui.input("New password (optional)").props(
                "type=password"
            ).classes("w-full")

            with ui.row().classes("justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close)

                def save() -> None:
                    if not name.value:
                        ui.notify("Username required", type="warning")
                        return
                    try:
                        self.repo.update_user(
                            sel["id"],
                            name.value,
                            _csv_to_roles(roles.value),
                            new_pw.value or None,
                        )
                        ui.notify("User updated")
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f"DB error: {e}", type="negative")

                ui.button("Save", on_click=save).props("color=primary")

        dialog.open()

    def open_delete_dialog(self) -> None:
        sel = self.selected_row()
        if not sel:
            ui.notify("Select a row first", type="warning")
            return

        with ui.dialog() as dialog, ui.card():
            deleted = True if sel.get("deleted_at") else False
            label_text = "Undelete" if deleted else "Soft-delete"

            ui.label(
                f'{label_text} user "{sel["username"]}"?'
            ).classes("text-lg")

            with ui.row().classes("justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close)

                def delete() -> None:
                    try:
                        self.repo.soft_delete_user(sel["id"], deleted is False)
                        ui.notify(
                            "User undeleted"
                            if deleted
                            else "User soft-deleted"
                        )
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f"DB error: {e}", type="negative")

                ui.button(label_text, on_click=delete).props("color=negative")

        dialog.open()
