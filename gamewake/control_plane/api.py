from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gamewake.accounts import (
    Account,
    ActivityEvent,
    CustomRole,
    Invitation,
    Membership,
    Permission,
    PredefinedRole,
    SensitiveActionConfirmation,
)
from gamewake.billing import Wallet, WalletContribution
from gamewake.game_catalog import GameTemplateDefinition
from gamewake.worlds import Backup, ConfigurationRevision, World, WorldExport, WorldOperation

from .application import GameWakeApplication
from .contracts import ConnectionDetails


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    user_id: str
    body: dict[str, Any] = field(default_factory=dict)
    authenticated_at: datetime | None = None


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: dict[str, Any]


class GameWakeApi:
    def __init__(self, application: GameWakeApplication) -> None:
        self._application = application

    def handle(self, request: ApiRequest) -> ApiResponse:
        try:
            return self._dispatch(request)
        except PermissionError as error:
            return ApiResponse(403, {"error": {"code": "forbidden", "message": str(error)}})
        except KeyError:
            return ApiResponse(404, {"error": {"code": "not_found", "message": "Not found"}})
        except (TypeError, ValueError) as error:
            return ApiResponse(
                400,
                {"error": {"code": "invalid_request", "message": str(error)}},
            )

    def _dispatch(self, request: ApiRequest) -> ApiResponse:
        parts = tuple(part for part in request.path.strip("/").split("/") if part)
        if request.method == "GET" and parts == ("api", "v1", "me", "accounts"):
            accounts = self._application.list_accounts(viewer_user_id=request.user_id)
            return ApiResponse(
                200,
                {"accounts": [self._account(account) for account in accounts]},
            )
        if parts[:3] != ("api", "v1", "accounts"):
            raise KeyError(request.path)
        if request.method == "POST" and len(parts) == 3:
            account = self._application.create_account(
                actor_user_id=request.user_id,
                name=self._required_string(request.body, "name"),
                discord_guild_id=self._optional_string(request.body, "discordGuildId"),
            )
            return ApiResponse(201, {"account": self._account(account)})
        if len(parts) < 4:
            raise KeyError(request.path)
        account_id = parts[3]
        if request.method == "GET" and parts[4:] == ("memberships",):
            memberships = self._application.list_memberships(
                account_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(
                200,
                {"memberships": [self._membership(item) for item in memberships]},
            )
        if request.method == "GET" and parts[4:] == ("roles",):
            roles = self._application.list_custom_roles(
                account_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(
                200,
                {
                    "predefinedRoles": ["owner", "manager", "player"],
                    "customRoles": [self._custom_role(item) for item in roles],
                    "permissions": sorted(permission.value for permission in Permission),
                },
            )
        if request.method == "POST" and parts[4:] == ("roles",):
            if request.authenticated_at is None:
                raise PermissionError("creating roles requires recent Discord authentication")
            raw_permissions = request.body.get("permissions")
            if not isinstance(raw_permissions, list) or not raw_permissions:
                raise ValueError("permissions must contain at least one permission")
            role = self._application.create_custom_role(
                account_id,
                actor_user_id=request.user_id,
                name=self._required_string(request.body, "name"),
                permissions={Permission(str(value)) for value in raw_permissions},
                confirmation=SensitiveActionConfirmation(
                    actor_user_id=request.user_id,
                    reauthenticated_at=request.authenticated_at,
                    confirmed_resource_name=self._required_string(
                        request.body, "confirmedResourceName"
                    ),
                ),
            )
            return ApiResponse(201, {"role": self._custom_role(role)})
        if (
            request.method == "POST"
            and len(parts) == 7
            and parts[4] == "memberships"
            and parts[6] == "roles"
        ):
            if request.authenticated_at is None:
                raise PermissionError("assigning roles requires recent Discord authentication")
            confirmation = SensitiveActionConfirmation(
                actor_user_id=request.user_id,
                reauthenticated_at=request.authenticated_at,
                confirmed_resource_name=self._required_string(
                    request.body, "confirmedResourceName"
                ),
            )
            custom_role_id = self._optional_string(request.body, "customRoleId")
            predefined_role = self._optional_string(request.body, "predefinedRole")
            if (custom_role_id is None) == (predefined_role is None):
                raise ValueError("choose exactly one predefinedRole or customRoleId")
            if custom_role_id is not None:
                membership = self._application.assign_custom_role(
                    account_id,
                    actor_user_id=request.user_id,
                    membership_id=parts[5],
                    custom_role_id=custom_role_id,
                    world_id=self._optional_string(request.body, "worldId"),
                    confirmation=confirmation,
                )
            else:
                membership = self._application.assign_predefined_role(
                    account_id,
                    actor_user_id=request.user_id,
                    membership_id=parts[5],
                    role=PredefinedRole(str(predefined_role)),
                    world_id=self._optional_string(request.body, "worldId"),
                    confirmation=confirmation,
                )
            return ApiResponse(200, {"membership": self._membership(membership)})
        if request.method == "GET" and parts[4:] == ("activity",):
            events = self._application.list_activity(
                account_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"events": [self._activity(item) for item in events]})
        if request.method == "GET" and parts[4:] == ("wallet",):
            wallet = self._application.get_wallet(account_id, viewer_user_id=request.user_id)
            return ApiResponse(200, {"wallet": self._wallet(wallet)})
        if request.method == "POST" and parts[4:] == ("wallet", "contributions"):
            contribution = self._application.create_contribution(
                account_id,
                payer_user_id=request.user_id,
                package_id=self._required_string(request.body, "packageId"),
                return_url=self._required_string(request.body, "returnUrl"),
                completion_url=self._required_string(request.body, "completionUrl"),
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(201, {"contribution": self._contribution(contribution)})
        if request.method == "POST" and parts[4:] == ("invitations",):
            invited_user_ids = request.body.get("invitedUserIds")
            if (
                not isinstance(invited_user_ids, list)
                or not invited_user_ids
                or not all(isinstance(item, str) and item for item in invited_user_ids)
            ):
                raise ValueError("invitedUserIds must contain at least one User ID")
            invitations = self._application.invite_friends(
                account_id,
                actor_user_id=request.user_id,
                invited_user_ids=invited_user_ids,
            )
            return ApiResponse(
                201,
                {"invitations": [self._invitation(item) for item in invitations]},
            )
        if (
            request.method == "POST"
            and len(parts) == 7
            and parts[4] == "invitations"
            and parts[6] == "accept"
        ):
            membership = self._application.accept_invitation(
                account_id,
                parts[5],
                invited_user_id=request.user_id,
            )
            return ApiResponse(200, {"membership": self._membership(membership)})
        if request.method == "POST" and parts[4:] == ("worlds",):
            world = self._application.create_world(
                account_id,
                actor_user_id=request.user_id,
                name=self._required_string(request.body, "name"),
                game_template_id=self._required_string(request.body, "gameTemplateId"),
                region=self._required_string(request.body, "region"),
                runtime_profile_id=self._required_string(request.body, "runtimeProfileId"),
            )
            return ApiResponse(201, {"world": self._world(world)})
        if request.method == "GET" and parts[4:] == ("worlds",):
            worlds = self._application.list_worlds(
                account_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"worlds": [self._world(world) for world in worlds]})
        if len(parts) < 6 or parts[4] != "worlds":
            raise KeyError(request.path)
        world_id = parts[5]
        if request.method == "GET" and parts[6:] == ("wake", "estimate"):
            estimate = self._application.wake_estimate(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"estimate": estimate})
        if request.method == "POST" and parts[6:] == ("wake",):
            operation = self._application.request_wake(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(202, {"operation": self._operation(operation)})
        if request.method == "POST" and parts[6:] == ("sleep",):
            operation = self._application.request_sleep(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
                force=request.body.get("force") is True,
            )
            return ApiResponse(202, {"operation": self._operation(operation)})
        if request.method == "GET" and parts[6:] == ("operations",):
            operations = self._application.worlds.list_operations(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(
                200,
                {"operations": [self._operation(operation) for operation in operations]},
            )
        if request.method == "GET" and parts[6:] == ("connection",):
            details = self._application.connection_details(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"connection": self._connection(details)})
        if request.method == "GET" and parts[6:] == ("configuration", "schema"):
            template = self._application.configuration_schema(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"template": self._template(template)})
        if request.method == "GET" and parts[6:] == ("configuration",):
            revision = self._application.effective_configuration(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"revision": self._revision(revision)})
        if request.method == "GET" and parts[6:] == ("backups",):
            backups = self._application.list_backups(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"backups": [self._backup(item) for item in backups]})
        if request.method == "POST" and parts[6:] == ("backups",):
            backup = self._application.create_manual_backup(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(201, {"backup": self._backup(backup)})
        if (
            request.method == "POST"
            and len(parts) == 9
            and parts[6] == "backups"
            and parts[8] == "restore"
        ):
            world = self._application.restore_backup(
                account_id,
                world_id,
                parts[7],
                actor_user_id=request.user_id,
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(200, {"world": self._world(world)})
        if request.method == "POST" and parts[6:] == ("exports",):
            export = self._application.create_world_export(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(201, {"export": self._export(export)})
        if request.method == "DELETE" and len(parts) == 6:
            if request.authenticated_at is None:
                raise PermissionError("deleting a World requires recent Discord authentication")
            world = self._application.schedule_world_deletion(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                confirmation=SensitiveActionConfirmation(
                    actor_user_id=request.user_id,
                    reauthenticated_at=request.authenticated_at,
                    confirmed_resource_name=self._required_string(
                        request.body, "confirmedResourceName"
                    ),
                ),
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
            )
            return ApiResponse(202, {"world": self._world(world)})
        if request.method == "POST" and parts[6:] == ("deletion", "cancel"):
            world = self._application.cancel_world_deletion(
                account_id,
                world_id,
                actor_user_id=request.user_id,
            )
            return ApiResponse(200, {"world": self._world(world)})
        if request.method == "PATCH" and parts[6:] == ("configuration",):
            world, revision = self._application.update_configuration(
                account_id,
                world_id,
                actor_user_id=request.user_id,
                changes=request.body.get("changes"),
                idempotency_key=self._required_string(request.body, "idempotencyKey"),
                origin="web",
            )
            return ApiResponse(
                200,
                {"world": self._world(world), "revision": self._revision(revision)},
            )
        raise KeyError(request.path)

    @staticmethod
    def _required_string(body: dict[str, Any], key: str) -> str:
        value = body.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} is required")
        return value

    @staticmethod
    def _optional_string(body: dict[str, Any], key: str) -> str | None:
        value = body.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _account(account: Account) -> dict[str, Any]:
        return {
            "id": account.id,
            "name": account.name,
            "discordGuildId": account.discord_guild_id,
        }

    @staticmethod
    def _invitation(invitation: Invitation) -> dict[str, Any]:
        return {
            "id": invitation.id,
            "accountId": invitation.account_id,
            "invitedUserId": invitation.invited_user_id,
            "status": invitation.status.value,
        }

    @staticmethod
    def _world(world: World) -> dict[str, Any]:
        return {
            "id": world.id,
            "accountId": world.account_id,
            "name": world.name,
            "gameTemplateId": world.game_template_id,
            "region": world.region,
            "runtimeProfileId": world.runtime_profile_id,
            "status": world.status.value,
            "configurationRevisionId": world.configuration_revision_id,
            "pendingConfigurationRevisionId": world.pending_configuration_revision_id,
            "storedStateId": world.stored_state_id,
            "deletionScheduledFor": (
                world.deletion_scheduled_for.isoformat()
                if world.deletion_scheduled_for is not None
                else None
            ),
        }

    @staticmethod
    def _membership(membership: Membership) -> dict[str, Any]:
        return {
            "id": membership.id,
            "accountId": membership.account_id,
            "userId": membership.user_id,
            "roles": [
                {
                    "id": assignment.id,
                    "role": (
                        assignment.predefined_role.value
                        if assignment.predefined_role is not None
                        else assignment.custom_role_id
                    ),
                    "kind": ("predefined" if assignment.predefined_role is not None else "custom"),
                    "worldId": assignment.scope.world_id,
                }
                for assignment in membership.assignments
            ],
        }

    @staticmethod
    def _custom_role(role: CustomRole) -> dict[str, Any]:
        return {
            "id": role.id,
            "accountId": role.account_id,
            "name": role.name,
            "permissions": sorted(permission.value for permission in role.permissions),
        }

    @staticmethod
    def _activity(event: ActivityEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "actorUserId": event.actor_user_id,
            "action": event.action.value,
            "subjectId": event.subject_id,
            "occurredAt": event.occurred_at.isoformat(),
        }

    @staticmethod
    def _backup(backup: Backup) -> dict[str, Any]:
        return {
            "id": backup.id,
            "kind": backup.kind.value,
            "sizeBytes": backup.size_bytes,
            "checksumVerified": bool(backup.checksum),
            "createdAt": backup.created_at.isoformat() if backup.created_at else None,
        }

    @staticmethod
    def _export(export: WorldExport) -> dict[str, Any]:
        return {
            "id": export.id,
            "downloadUrl": export.download_url,
            "createdAt": export.created_at.isoformat(),
            "formatVersion": export.manifest.format_version,
        }

    @staticmethod
    def _revision(revision: ConfigurationRevision) -> dict[str, Any]:
        return {
            "id": revision.id,
            "number": revision.number,
            "values": dict(revision.entries),
            "actorUserId": revision.actor_user_id,
            "origin": revision.origin,
            "createdAt": revision.created_at.isoformat(),
        }

    @staticmethod
    def _operation(operation: WorldOperation) -> dict[str, Any]:
        return {
            "id": operation.id,
            "accountId": operation.account_id,
            "worldId": operation.world_id,
            "type": operation.operation_type.value,
            "status": operation.status.value,
            "phase": operation.phase.value,
            "createdAt": operation.created_at.isoformat(),
        }

    @staticmethod
    def _wallet(wallet: Wallet) -> dict[str, Any]:
        return {
            "accountId": wallet.account_id,
            "currency": wallet.currency,
            "balance": str(wallet.balance),
            "availableBalance": str(wallet.available_balance),
            "statement": [
                {
                    "id": entry.id,
                    "type": entry.entry_type.value,
                    "amount": str(entry.amount),
                    "reference": entry.reference,
                    "occurredAt": entry.occurred_at.isoformat(),
                }
                for entry in wallet.statement
            ],
        }

    @staticmethod
    def _contribution(contribution: WalletContribution) -> dict[str, Any]:
        return {
            "id": contribution.id,
            "accountId": contribution.account_id,
            "packageId": contribution.package_id,
            "amount": str(contribution.amount),
            "status": contribution.status.value,
            "checkoutUrl": contribution.checkout_url,
            "createdAt": contribution.created_at.isoformat(),
        }

    @staticmethod
    def _connection(details: ConnectionDetails) -> dict[str, Any]:
        return {
            "host": details.host,
            "port": details.port,
            "password": details.password,
        }

    @staticmethod
    def _template(template: GameTemplateDefinition) -> dict[str, Any]:
        return {
            "id": template.id,
            "displayName": template.display_name,
            "configurationFields": [
                {
                    "key": item.key,
                    "iniKey": item.ini_key,
                    "label": item.label_pt,
                    "section": item.section,
                    "valueType": item.value_type,
                    "default": item.default,
                    "recommended": item.recommended,
                    "acceptedValues": item.allowed_values_pt,
                    "impact": item.impact_pt,
                    "officialDocumentationUrl": item.official_documentation_url,
                    "restartRequired": item.restart_required,
                    "choices": list(item.choices),
                }
                for item in template.configuration_fields
            ],
        }
