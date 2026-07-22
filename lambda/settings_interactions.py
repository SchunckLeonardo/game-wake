"""Native Discord panel and modal flow for Palworld settings."""

from __future__ import annotations

import logging
from typing import Any

from palworld_settings_catalog import (
    FIELDS,
    FIELDS_BY_KEY,
    OFFICIAL_CONFIGURATION_URL,
    SECTIONS,
    SettingField,
    SettingsValidationError,
)
from response_service import message, modal, rich_message

APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3
MODAL_SUBMIT = 5
SETTING_SELECT_ID = "pwcfg:setting"
VALUE_INPUT_ID = "pwcfg:value"
EDIT_MODAL_PREFIX = "pwcfg:edit:"
LOGGER = logging.getLogger(__name__)

SECTION_LABELS = {
    "Server": "Servidor",
    "Base and Palbox": "Base e Palbox",
    "Gameplay": "Jogabilidade",
    "Damage": "Dano",
    "Stamina and inventory": "Stamina e inventário",
}


def _display_value(value: object, *, limit: int = 72) -> str:
    rendered = f"{value:g}" if isinstance(value, float) else str(value)
    rendered = rendered.replace("`", "'").replace("\n", " ")
    if len(rendered) > limit:
        return rendered[: limit - 1] + "…"
    return rendered


def _form_value(value: object) -> str:
    rendered = f"{value:g}" if isinstance(value, float) else str(value)
    return rendered[:4000]


def _select_options() -> list[dict[str, Any]]:
    return [
        {
            "label": field.label_pt,
            "value": field.key,
            "description": field.menu_description_pt,
        }
        for field in FIELDS
    ]


def _settings_embed(snapshot: Any) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    for section in SECTIONS:
        lines = []
        for field in FIELDS:
            if field.section != section:
                continue
            source = " · **Discord**" if snapshot.source(field.key) == "discord" else ""
            lines.append(
                f"`{field.ini_key}`: **{_display_value(snapshot.effective[field.key])}**{source}"
            )
        fields.append(
            {
                "name": SECTION_LABELS[section],
                "value": "\n".join(lines),
                "inline": False,
            }
        )

    return {
        "title": "⚙️ Configurações do servidor Palworld",
        "url": OFFICIAL_CONFIGURATION_URL,
        "description": (
            "Escolha uma configuração no menu. O formulário mostra os valores aceitos, "
            "a explicação oficial e o valor atual. Alterações marcadas como **Discord** "
            "sobrescrevem a base do repositório."
        ),
        "color": 0x5865F2,
        "fields": fields,
        "footer": {"text": "Use PADRAO no formulário para remover um override do Discord."},
    }


def _text_input(field: SettingField, current_value: object) -> dict[str, Any]:
    return {
        "type": 4,
        "custom_id": VALUE_INPUT_ID,
        "style": 2 if field.key == "server_description" else 1,
        "min_length": 0 if field.allow_empty else 1,
        "max_length": field.max_length or 4000,
        "required": not field.allow_empty,
        "value": _form_value(current_value),
        "placeholder": "Digite PADRAO para restaurar o valor da base",
    }


def _choice_input(field: SettingField, current_value: object) -> dict[str, Any]:
    help_by_choice = field.choice_help_pt
    options = [
        {
            "label": choice,
            "value": choice,
            "description": help_by_choice[choice],
            "default": choice.casefold() == str(current_value).casefold(),
        }
        for choice in field.choices
    ]
    options.append(
        {
            "label": "Padrão do repositório",
            "value": "__default__",
            "description": "Remove a alteração feita pelo Discord.",
        }
    )
    return {
        "type": 3,
        "custom_id": VALUE_INPUT_ID,
        "options": options,
        "min_values": 1,
        "max_values": 1,
        "required": True,
    }


def _walk_components(value: object):
    if isinstance(value, dict):
        yield value
        component = value.get("component")
        if component is not None:
            yield from _walk_components(component)
        for child in value.get("components", []):
            yield from _walk_components(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_components(child)


def _submitted_value(interaction: dict[str, Any]) -> object:
    components = (interaction.get("data") or {}).get("components") or []
    for component in _walk_components(components):
        if component.get("custom_id") != VALUE_INPUT_ID:
            continue
        if "value" in component:
            return component["value"]
        values = component.get("values") or []
        if len(values) == 1:
            return values[0]
    raise SettingsValidationError("missing modal value")


def is_settings_interaction(interaction: dict[str, Any]) -> bool:
    interaction_type = interaction.get("type")
    data = interaction.get("data") or {}
    if interaction_type == MESSAGE_COMPONENT:
        return str(data.get("custom_id") or "").startswith("pwcfg:")
    if interaction_type == MODAL_SUBMIT:
        return str(data.get("custom_id") or "").startswith(EDIT_MODAL_PREFIX)
    return False


class SettingsInteractionController:
    """One small interface hiding Discord UI, validation, persistence and activation."""

    def __init__(self, settings_service: Any, game_service: Any):
        self._settings = settings_service
        self._game = game_service

    def handle(self, interaction: dict[str, Any]) -> dict[str, Any]:
        interaction_type = interaction.get("type")
        if interaction_type == APPLICATION_COMMAND:
            return self._panel()
        if interaction_type == MESSAGE_COMPONENT:
            return self._select_setting(interaction)
        if interaction_type == MODAL_SUBMIT:
            return self._save_setting(interaction)
        return message("Interação de configuração não suportada.", ephemeral=True)

    def _panel(self) -> dict[str, Any]:
        snapshot = self._settings.read()
        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": SETTING_SELECT_ID,
                        "placeholder": "Escolha uma configuração para alterar",
                        "min_values": 1,
                        "max_values": 1,
                        "options": _select_options(),
                    }
                ],
            },
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Documentação oficial do Palworld",
                        "url": OFFICIAL_CONFIGURATION_URL,
                    }
                ],
            },
        ]
        return rich_message(
            f"Guia oficial: {OFFICIAL_CONFIGURATION_URL}",
            embeds=[_settings_embed(snapshot)],
            components=components,
            ephemeral=True,
        )

    def _select_setting(self, interaction: dict[str, Any]) -> dict[str, Any]:
        data = interaction.get("data") or {}
        values = data.get("values") or []
        if data.get("custom_id") != SETTING_SELECT_ID or len(values) != 1:
            return message("Controle de configuração inválido.", ephemeral=True)
        key = str(values[0])
        field = FIELDS_BY_KEY.get(key)
        if field is None:
            return message("Configuração desconhecida.", ephemeral=True)

        snapshot = self._settings.read()
        source = "Discord" if snapshot.source(key) == "discord" else "base do repositório"
        help_text = (
            f"**Valores aceitos:** {field.allowed_values_pt}\n"
            f"{field.official_description_pt}\n"
            f"Valor atual vindo de **{source}**.\n"
            f"[Documentação oficial do Palworld]({OFFICIAL_CONFIGURATION_URL})"
        )
        value_component = (
            _choice_input(field, snapshot.effective[key])
            if field.value_type in {"choice", "boolean"}
            else _text_input(field, snapshot.effective[key])
        )
        return modal(
            f"{EDIT_MODAL_PREFIX}{key}",
            field.label_pt[:45],
            [
                {"type": 10, "content": help_text},
                {
                    "type": 18,
                    "label": field.label_pt,
                    "description": field.menu_description_pt,
                    "component": value_component,
                },
            ],
        )

    def _save_setting(self, interaction: dict[str, Any]) -> dict[str, Any]:
        custom_id = str((interaction.get("data") or {}).get("custom_id") or "")
        key = custom_id.removeprefix(EDIT_MODAL_PREFIX)
        field = FIELDS_BY_KEY.get(key)
        if not custom_id.startswith(EDIT_MODAL_PREFIX) or field is None:
            return message("Formulário de configuração inválido.", ephemeral=True)

        try:
            raw_value = _submitted_value(interaction)
            snapshot = self._settings.set_override(key, raw_value)
        except SettingsValidationError:
            return message(
                f"❌ Valor inválido para **{field.label_pt}**.\n"
                f"Valores aceitos: {field.allowed_values_pt}\n"
                f"Guia oficial: {OFFICIAL_CONFIGURATION_URL}",
                ephemeral=True,
            )

        restored = snapshot.source(key) == "base"
        source_text = "base do repositório" if restored else "override do Discord"
        activation_text = self._request_activation()
        return message(
            f"✅ **{field.label_pt}** agora é "
            f"`{_display_value(snapshot.effective[key], limit=256)}` "
            f"({source_text}).\n{activation_text}",
            ephemeral=True,
        )

    def _request_activation(self) -> str:
        try:
            command_id = self._game.request_settings_activation()
            return (
                f"Uma ativação segura foi solicitada (`{command_id[:8]}`). "
                "Se houver jogadores conectados ou a consulta falhar, o servidor não será "
                "reiniciado e a alteração ficará pronta para a próxima inicialização segura."
            )
        except Exception:
            LOGGER.warning("settings activation deferred", exc_info=True)
            return (
                "A alteração foi salva, mas não foi possível solicitar a ativação agora; "
                "ela ficará pronta para a próxima inicialização segura."
            )
