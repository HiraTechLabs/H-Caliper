"""Role-based access control and project isolation at the API boundary."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio

from conftest import (  # noqa: E402
    API,
    MEMBER_PASSWORD,
    create_project_via_api,
    create_task_via_api,
    create_user_via_api,
    csrf_headers,
    login,
    make_client,
    setup_pipeline_project,
)


async def test_admin_only_endpoints_reject_operator_and_viewer(admin_client):
    operator = await create_user_via_api(
        admin_client, email="operator@example.com", role="OPERATOR"
    )
    viewer = await create_user_via_api(
        admin_client, email="viewer@example.com", role="VIEWER"
    )

    async with make_client() as operator_client:
        await login(operator_client, operator["email"], MEMBER_PASSWORD)
        create_provider = await operator_client.post(
            f"{API}/providers",
            headers=csrf_headers(operator_client),
            json={"name": "Forbidden Provider", "type": "mock"},
        )
        assert create_provider.status_code == 403
        audit = await operator_client.get(f"{API}/audit")
        assert audit.status_code == 403

    async with make_client() as viewer_client:
        await login(viewer_client, viewer["email"], MEMBER_PASSWORD)
        audit = await viewer_client.get(f"{API}/audit")
        assert audit.status_code == 403
        create_project = await viewer_client.post(
            f"{API}/projects",
            headers=csrf_headers(viewer_client),
            json={"name": "Viewer Project"},
        )
        assert create_project.status_code == 403

    admin_audit = await admin_client.get(f"{API}/audit")
    assert admin_audit.status_code == 200
    assert "items" in admin_audit.json()


async def test_project_isolation_and_member_role_write_rules(admin_client, local_repo):
    configured = await setup_pipeline_project(admin_client, local_repo)
    project_id = configured["project"]["id"]

    private = await create_project_via_api(
        admin_client, name="Private Isolation Project"
    )

    operator = await create_user_via_api(
        admin_client, email=f"operator-{uuid.uuid4().hex[:6]}@example.com", role="OPERATOR"
    )
    viewer = await create_user_via_api(
        admin_client, email=f"viewer-{uuid.uuid4().hex[:6]}@example.com", role="VIEWER"
    )

    async with make_client() as operator_client:
        await login(operator_client, operator["email"], MEMBER_PASSWORD)

        # Not a member of the private project: reads and writes are forbidden.
        denied_read = await operator_client.get(f"{API}/projects/{private['id']}")
        assert denied_read.status_code == 403
        denied_task = await operator_client.post(
            f"{API}/tasks",
            headers=csrf_headers(operator_client),
            json={
                "project_id": private["id"],
                "title": "Should never be created",
                "description": "This request is denied before project access.",
            },
        )
        assert denied_task.status_code == 403

        # Being added as a member unlocks reads but not admin-only operations.
        added = await admin_client.post(
            f"{API}/projects/{project_id}/members",
            headers=csrf_headers(admin_client),
            json={"user_id": operator["id"], "role": "OPERATOR"},
        )
        assert added.status_code == 201
        assert (await operator_client.get(f"{API}/projects/{project_id}")).status_code == 200

        operator_task = await create_task_via_api(
            operator_client, project_id, title="Operator-created fixture task"
        )
        assert operator_task["project_id"] == project_id

        # Global OPERATOR role does not override a project-level VIEWER role.
        await admin_client.post(
            f"{API}/projects/{project_id}/members",
            headers=csrf_headers(admin_client),
            json={"user_id": operator["id"], "role": "VIEWER"},
        )
        denied_settings = await operator_client.patch(
            f"{API}/projects/{project_id}",
            headers=csrf_headers(operator_client),
            json={"description": "must remain unchanged"},
        )
        assert denied_settings.status_code == 403

    async with make_client() as viewer_client:
        await login(viewer_client, viewer["email"], MEMBER_PASSWORD)
        added = await admin_client.post(
            f"{API}/projects/{project_id}/members",
            headers=csrf_headers(admin_client),
            json={"user_id": viewer["id"], "role": "VIEWER"},
        )
        assert added.status_code == 201

        assert (await viewer_client.get(f"{API}/projects/{project_id}")).status_code == 200
        viewer_task = await viewer_client.post(
            f"{API}/tasks",
            headers=csrf_headers(viewer_client),
            json={
                "project_id": project_id,
                "title": "Viewer must not create tasks",
                "description": "Viewers are read-only even as project members.",
            },
        )
        assert viewer_task.status_code == 403
        viewer_project_update = await viewer_client.patch(
            f"{API}/projects/{project_id}",
            headers=csrf_headers(viewer_client),
            json={"description": "viewer must not update project settings"},
        )
        assert viewer_project_update.status_code == 403

    admin_task = await create_task_via_api(
        admin_client, project_id, title="Administrator-created fixture task"
    )
    assert admin_task["project_id"] == project_id

    listed = await admin_client.get(f"{API}/tasks", params={"project_id": project_id})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2
