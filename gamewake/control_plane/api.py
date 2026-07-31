from dataclasses import dataclass, field
from typing import Any

from gamewake.accounts import Account, Invitation
from gamewake.game_catalog import GameTemplateDefinition
from gamewake.worlds import ConfigurationRevision, World

from .application import GameWakeApplication


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    user_id: str
    body: dict[str, Any] = field(default_factory=dict)


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
        if len(parts) < 6 or parts[4] != "worlds":
            raise KeyError(request.path)
        world_id = parts[5]
        if request.method == "GET" and parts[6:] == ("configuration", "schema"):
            template = self._application.configuration_schema(
                account_id,
                world_id,
                viewer_user_id=request.user_id,
            )
            return ApiResponse(200, {"template": self._template(template)})
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
