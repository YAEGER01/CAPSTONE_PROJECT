# TODO - Logout + President sidebar button

- [x] Add logout view in `core_system/views.py` to revoke ACCESS_SESSION and clear session keys.

- [x] Add `logout` URL route + `name="logout"` in `core_system/urls.py`.
- [x] Add logout button/link in `templates/website/President/base.html` sidebar.

- [ ] Test: login -> logout -> redirected to login; protected pages redirect to login.
