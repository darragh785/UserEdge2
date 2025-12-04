# edge_page.py
from __future__ import annotations

from typing import Dict, List, Optional

from nicegui import ui

from domain_models import Edge, User
from db_connector_pg import PostgresConnector


class EdgesPage:
    """NiceGUI page for listing + CRUD on edges (with single-owner assignment)."""

    def __init__(self, repo: PostgresConnector, *, owner_filter_user_id: Optional[str] = None):
        self.repo = repo
        # optional filter (used when jumping from Users later)
        self._owner_filter_user_id: Optional[str] = owner_filter_user_id
        self._owner_options: List[Dict[str, str]] = []

        ui.page_title('Edges Admin')

        # ---------- header row ----------
        with ui.row().classes('bg-teal-600 text-white items-center px-3 py-2 rounded w-full'):
            ui.label('Edges Admin').classes('text-xl font-semibold')
            ui.space()

            # A compact owner filter (optional). Ready for Users->Edges navigation.
            self.owner_filter = ui.select(
                options=self._owner_options,
                label='Owner filter',
                value=None,
            ).props('clearable dense options-dense').classes('w-[260px]')
            self.owner_filter.on_value_change(lambda e: self._set_owner_filter(e.value))

        # search input bound to table filter (same pattern as Users)
        search = ui.input('Search').classes('mt-2')

        # ---------- main table ----------
        self.table = ui.table(
            columns=[
                {'name': 'id',             'label': 'UUID',    'field': 'id'},
                {'name': 'serial_number',  'label': 'Serial',  'field': 'serial_number', 'sortable': True},
                {'name': 'type',           'label': 'Type',    'field': 'type',          'sortable': True},
                {'name': 'owner',          'label': 'Owner',   'field': 'owner',         'sortable': True},
                {'name': 'updated_at',     'label': 'Updated', 'field': 'updated_at',    'sortable': True},
            ],
            rows=[],
            row_key='id',
        ).classes('w-full mt-2').props('selection="single"')

        self.table.on('selection', self.update_buttons)
        search.bind_value(self.table, 'filter')

        # ---------- action buttons ----------
        with ui.row().classes('gap-2 my-2'):
            self.btn_add = ui.button('Add edge', on_click=self.open_add_dialog)
            self.btn_edit = ui.button('Edit', on_click=self.open_edit_dialog)
            self.btn_edit.disable()
            self.btn_del = ui.button('Delete', on_click=self.open_delete_dialog).props('color=negative')
            self.btn_del.disable()

        # preload owner options & initial data
        self._load_owner_options()

        # initialise the filter value if provided
        if self._owner_filter_user_id:
            self.owner_filter.value = str(self._owner_filter_user_id)
            self.owner_filter.update()

        self.refresh()

    # ---------- data & state ---------
    def _load_owner_options(self) -> None:
        """Populate the Owner dropdowns from active users (for assignment and filtering)."""
        try:
            # Typically we only show active users when *assigning* an owner
            users: List[User] = self.repo.get_all_users()
        except Exception as e:
            users = []
            ui.notify(f'Owner list error: {e}', type='negative')

        # For selects we use [{'label': username, 'value': id}, ...]
        self._owner_options = [
            {'label': u.username, 'value': str(u.id)}
            for u in users
            if u.id is not None
        ]

        # Filter select: allow "(All owners)" or a specific user
        filter_opts = [{'label': '(All owners)', 'value': None}] + self._owner_options
        self.owner_filter.options = filter_opts
        self.owner_filter.update()

    def refresh(self) -> None:
        """Reload the table rows from DB."""
        try:
            edges: List[Edge] = self.repo.get_all_edges(owner_id=self._owner_filter_user_id)
            rows = [e.to_ui_row() for e in edges]
        except Exception as e:
            rows = []
            ui.notify(f'DB error: {e}', type='negative')

        self.table.rows = rows
        self.table.update()

        if hasattr(self.table, 'selected'):
            self.table.selected = []
        self.update_buttons()

    def selected_row(self) -> Optional[Dict]:
        sel = getattr(self.table, 'selected', [])
        return sel[0] if sel else None

    def update_buttons(self, e=None) -> None:
        self.btn_edit.disable()
        self.btn_del.disable()
        if bool(getattr(self.table, 'selected', [])):
            self.btn_edit.enable()
            self.btn_del.enable()
        self.btn_edit.update()
        self.btn_del.update()

    def _set_owner_filter(self, owner_user_id: Optional[str]) -> None:
        self._owner_filter_user_id = owner_user_id or None
        self.refresh()

    # ---------- dialogs ---------
    def open_add_dialog(self) -> None:
        with ui.dialog() as dialog, ui.card().classes('w-[520px]'):
            ui.label('Add edge').classes('text-lg')

            serial_number = ui.input('Serial number').classes('w-full')
            typ = ui.input('Type').classes('w-full')

            owner = ui.select(
                options=self._owner_options,
                label='Owner (optional)',
            ).props('clearable options-dense').classes('w-full')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def save() -> None:
                    if not serial_number.value or not typ.value:
                        ui.notify('Serial number and type are required', type='warning')
                        return
                    try:
                        edge_id = self.repo.create_edge(
                            serial_number.value.strip(),
                            typ.value.strip(),
                        )
                        # set owner if any
                        self.repo.set_edge_owner_id(edge_id, owner.value or None)
                        ui.notify('Edge created')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Save', on_click=save).props('color=primary')
        dialog.open()

    def open_delete_dialog(self) -> None:
        sel = self.selected_row()
        if not sel:
            ui.notify('Select a row first', type='warning')
            return

        with ui.dialog() as dialog, ui.card():
            ui.label(f'Delete edge "{sel["serial_number"]}"? (irreversible)').classes('text-lg')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def delete() -> None:
                    try:
                        self.repo.hard_delete_edge(sel['id'])
                        ui.notify('Edge deleted')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Delete', on_click=delete).props('color=negative')
        dialog.open()

    def open_edit_dialog(self) -> None:
        sel = self.selected_row()
        if not sel:
            ui.notify('Select a row first', type='warning')
            return

        # Pre-fill owner field by looking up current owner id
        current_owner_id: Optional[str] = None
        try:
            owner_id = self.repo.get_edge_owner_id(sel['id'])
            current_owner_id = str(owner_id) if owner_id is not None else None
        except Exception as e:
            ui.notify(f'Owner lookup error: {e}', type='warning')

        with ui.dialog() as dialog, ui.card().classes('w-[520px]'):
            ui.label(f'Edit edge: {sel["serial_number"]}').classes('text-lg')

            serial = ui.input('Serial number', value=sel['serial_number']).classes('w-full')
            typ = ui.input('Type', value=sel.get('type') or '').classes('w-full')

            owner = ui.select(
                options=self._owner_options,
                value=current_owner_id,
                label='Owner (optional)',
            ).props('clearable options-dense').classes('w-full')

            with ui.row().classes('justify-end gap-2 mt-2'):
                ui.button('Cancel', on_click=dialog.close)

                def save() -> None:
                    if not serial.value or not typ.value:
                        ui.notify('Serial number and type are required', type='warning')
                        return
                    try:
                        self.repo.update_edge(sel['id'], serial.value.strip(), typ.value.strip())
                        self.repo.set_edge_owner_id(sel['id'], owner.value or None)
                        ui.notify('Edge updated')
                        dialog.close()
                        self.refresh()
                    except Exception as e:
                        ui.notify(f'DB error: {e}', type='negative')

                ui.button('Save', on_click=save).props('color=primary')
        dialog.open()

    # ---------- helpers for integration with Users page ----------
    def show_edges_for_owner(self, owner_user_id: Optional[str]) -> None:
        """External entry point: set owner filter and refresh."""
        self.owner_filter.value = str(owner_user_id) if owner_user_id else None
        self.owner_filter.update()
        self._set_owner_filter(owner_user_id)

    def set_show_uuid(self, show: bool) -> None:
        """Show/hide the UUID column."""
        col_names = [c['name'] for c in self.table.columns]
        visible = col_names if show else [n for n in col_names if n != 'id']
        self.table.props(f'visible-columns={",".join(visible)}')
        self.table.update()
