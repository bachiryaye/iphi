import uuid

import pytest

from app.identity.auth_domain import Role, User


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("required", list(Role))
def test_server_role_permissions(role: Role, required: Role) -> None:
    user = User(uuid.uuid7(), "operator", "Operator", role)
    expected = required is Role.VIEWER or role is Role.ADMIN or role is required
    assert user.permits(required) is expected
