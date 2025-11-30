from typing import Dict, List, Optional

from nicegui import ui
from db_connector_pg import PostgresConnector


def _csv_to_roles(text: Optional[str]) -> List[str]:
    """Convert a comma-separated roles string to a list of trimmed role names."""
    return [r.strip() for r in (text or '').split(',') if r.strip()]


class UsersPage:
    def __init__(self, repo: PostgresConnector):
        self.repo = repo

        ui.page_title('Users Admin - Basic Version')

        # Header
        with ui.header().classes('bg-cyan-600 text-white'):
            # https://tailwindcss.com/docs/colors
            ui.label('Users Admin - Basic Version').classes('text-xl font-semibold')

        # Search input
        search = ui.input('Search')

        # Main table
        self.table = ui.table(
            columns=[
                {'name': 'id',         'label': 'UUID',    'field': 'id'},
                {'name': 'username',   'label': 'Username','field': 'username',   'sortable': True},
                {'name': 'roles',      'label': 'Roles',   'field': 'roles',      'sortable': True},
                {'name': 'updated_at', 'label': 'Updated', 'field': 'updated_at', 'sortable': True},
                {'name': 'deleted_at', 'label': 'Deleted', 'field': 'deleted_at', 'sortable': True},
            ],
            rows=[],
            row_key='id',
        ).classes('w-full mt-2').props('selection="single"')

        self.table.on('selection', self.update_buttons)
        search.bind_value(self.table, 'filter')

        # Action buttons
        with ui.row().classes('gap-2 my-2'):
            self.btn_add = ui.button('Add user', on_click=self.open_add_dialog)
            self.btn_edit = ui.button('Edit', on_click=self.open_edit_dialog)
            self.btn_edit.disable()
            self.btn_del = ui.button('Delete', on_click=self.open_delete_dialog).props('color=negative')
            self.btn_del.disable()
            self.btn_harddel = ui.button('Hard-delete', on_click=self.open_hard_delete_dialog).props('color=negative')
            self.btn_harddel.visible = False

        self.refresh()

    # ------------------------------------------------------------------
    # Data loading / table state
    # ------------------------------------------------------------------
    def refresh(self):
        """Reload table rows from the database."""
        self.table.rows = [u.to_ui_row() for u in self.repo.get_all_users()]
        self.table.update()
        if hasattr(self.table, 'selected'):
            self.table.selected = []
        self.update_buttons()

    def selected_row(self) -> Optional[Dict]:
        """Return the currently selected row dict or None."""
        sel = getattr(self.table, 'selected', [])
        return sel[0] if sel else None

    def update_buttons(self, e=None):
        """Enable/disable buttons based on selection + soft-delete state."""
        self.btn_edit.disable()
        self.btn_del.disable()
        self.btn_del.text = 'Delete'
        self.btn_harddel.visible = False

        if bool(getattr(self.table, 'selected', [])):
            self.btn_edit.enable()
            self.btn_del.enable()
            if self.selected_row().get('deleted_at'):
                self.btn_del.text = 'Undelete'
                self.btn_harddel.visible = True

        self.btn_edit.update()
        self.btn_del.update()
        self.btn_harddel.update()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def open_add_dialog(self):
        with ui.dialog() as dialog, ui.card().classes('w-[480px]'):
            ui.label('Add user').classes('text-lg')
            name = ui.input('Username').classes('w-full')
            pw = ui.input('Password').props('type=password').classes('w-full')
            roles = ui.input('Roles (comma-separated)').classes('w-full')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def save():
                    if not name.value or not pw.value:
                        ui.notify('Username and password required', type='warning')
                        return
                    try:
                        self.repo.create_user(
                            name.value,
                            pw.value,
                            _csv_to_roles(roles.value),
                        )
                        ui.notify('User created')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Save', on_click=save).props('color=primary')

        dialog.open()

    def open_edit_dialog(self):
        sel = self.selected_row()
        if not sel:
            ui.notify('Select a row first', type='warning')
            return

        with ui.dialog() as dialog, ui.card().classes('w-[480px]'):
            ui.label(f'Edit user: {sel["username"]}').classes('text-lg')
            name = ui.input('Username', value=sel['username']).classes('w-full')
            roles = ui.input(
                'Roles (comma-separated)',
                value=sel.get('roles') or '',
            ).classes('w-full')
            new_pw = ui.input('New password (optional)').props('type=password').classes('w-full')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def save():
                    if not name.value:
                        ui.notify('Username required', type='warning')
                        return
                    try:
                        self.repo.update_user(
                            sel['id'],
                            name.value,
                            _csv_to_roles(roles.value),
                            new_pw.value or None,
                        )
                        ui.notify('User updated')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Save', on_click=save).props('color=primary')

        dialog.open()

    def open_delete_dialog(self):
        sel = self.selected_row()
        if not sel:
            ui.notify('Select a row first', type='warning')
            return

        with ui.dialog() as dialog, ui.card():
            deleted = True if sel.get('deleted_at') else False
            label_text = 'Undelete' if deleted else 'Soft-delete'
            ui.label(f'{label_text} user "{sel["username"]}"?').classes('text-lg')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def delete():
                    try:
                        # delete==False → set deleted_at = now (soft-delete)
                        # delete==True  → set deleted_at = NULL (undelete)
                        self.repo.soft_delete_user(sel['id'], deleted is False)
                        ui.notify('User undeleted' if deleted else 'User soft-deleted')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button(label_text, on_click=delete).props('color=negative')

        dialog.open()

    def open_hard_delete_dialog(self):
        sel = self.selected_row()
        deleted = True if sel.get('deleted_at') else False
        if not sel or not deleted:
            ui.notify('Select a soft deleted row first', type='warning')
            return

        with ui.dialog() as dialog, ui.card():
            ui.label(f'Hard delete (irreversible) user "{sel["username"]}"?').classes('text-lg')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def delete():
                    try:
                        self.repo.hard_delete_user(sel['id'])
                        ui.notify('User hard-deleted')  # permanently gone
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Hard Delete', on_click=delete).props('color=negative')

        dialog.open()
