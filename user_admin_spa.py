from nicegui import ui
from user_page import UsersPage
from edge_page import EdgesPage


def register_admin_spa(repo):
    """Register the / admin SPA using the provided repo."""

    @ui.page('/')   # define the page when this function is called
    def admin_app():

        # ---------- Drawer / Navigation ----------
        drawer = ui.left_drawer(value=True).props('behavior=default').classes('bg-gray-100')

        with ui.header().classes('bg-slate-700 text-white'):
            ui.button(icon='menu', on_click=drawer.toggle).props('flat round')
            ui.label('Admin Console').classes('text-xl font-semibold')
            ui.space()
            show_uuid_cb = ui.checkbox('Show UUIDs', value=True).props('dense')

        # ---------- Views (only one visible at a time) ----------
        users_container = ui.element('div').classes('w-full')
        edges_container = ui.element('div').classes('w-full hidden')

        pages = {'users': None, 'edges': None}

        def show_view(name: str):
            """Switch between Users and Edges view."""
            if name == 'users':
                if pages.get('users') and hasattr(pages['users'], 'refresh'):
                    pages['users'].refresh()

                users_container.classes(remove='hidden')
                edges_container.classes(add='hidden')

            else:
                users_container.classes(add='hidden')
                edges_container.classes(remove='hidden')

        # When a user clicks "View Devices" from UsersPage
        def show_edge_with_filter_callback(owner_user_id: str):
            if pages['edges'] is not None:
                pages['edges'].show_edges_for_owner(owner_user_id)
            show_view('edges')

        # ---------- Drawer Buttons ----------
        with drawer:
            ui.button('Users', on_click=lambda: show_view('users')).classes('w-full px-4')
            ui.button('Edges', on_click=lambda: show_view('edges')).classes('w-full px-4')

        # ---------- Load the Pages ----------
        with users_container:
            pages['users'] = UsersPage(repo, on_view_devices=show_edge_with_filter_callback)

        with edges_container:
            pages['edges'] = EdgesPage(repo)

        # ---------- Show/hide UUID column globally ----------
        def _toggle_uuid(e):
            for p in pages.values():
                if p and callable(getattr(p, 'set_show_uuid', None)):
                    p.set_show_uuid(e.value)

        show_uuid_cb.on_value_change(_toggle_uuid)

        # Force initial UUID setting to apply on first load
        _toggle_uuid(type('Evt', (), {'value': show_uuid_cb.value})())

        # ---------- Start on Users Page ----------
        show_view('users')
