"""Canonical Palworld settings catalog shared by local and Discord interfaces."""

from __future__ import annotations

import math
from dataclasses import dataclass

OFFICIAL_CONFIGURATION_URL = "https://docs.palworldgame.com/settings-and-operation/configuration/"
SCHEMA_VERSION = 1


class SettingsValidationError(ValueError):
    """Raised when a supported setting cannot be safely normalized."""


@dataclass(frozen=True)
class SettingField:
    key: str
    ini_key: str
    label: str
    label_pt: str
    section: str
    value_type: str
    allowed_values_pt: str
    menu_description_pt: str
    official_description_pt: str
    minimum: float | None = None
    maximum: float | None = None
    minimum_inclusive: bool = False
    max_length: int | None = None
    choices: tuple[str, ...] = ()
    choice_descriptions_pt: tuple[tuple[str, str], ...] = ()
    allow_empty: bool = False

    def parse(self, value: object) -> str | int | float | bool:
        if self.value_type == "string":
            if not isinstance(value, str):
                raise SettingsValidationError(f"{self.label} must be text")
            parsed = value.strip() if not self.allow_empty else value
            if not parsed and not self.allow_empty:
                raise SettingsValidationError(f"{self.label} must not be empty")
            if self.max_length is not None and len(parsed) > self.max_length:
                raise SettingsValidationError(
                    f"{self.label} must be at most {self.max_length} characters"
                )
            return parsed

        if self.value_type == "choice":
            if not isinstance(value, str):
                raise SettingsValidationError(
                    f"{self.label} must be one of: {', '.join(self.choices)}"
                )
            choices_by_case = {choice.casefold(): choice for choice in self.choices}
            try:
                return choices_by_case[value.strip().casefold()]
            except KeyError as error:
                raise SettingsValidationError(
                    f"{self.label} must be one of: {', '.join(self.choices)}"
                ) from error

        if self.value_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().casefold()
                if normalized == "true":
                    return True
                if normalized == "false":
                    return False
            raise SettingsValidationError(f"{self.label} must be True or False")

        if isinstance(value, bool):
            raise SettingsValidationError(f"{self.label} must be a number")

        if self.value_type == "integer":
            if isinstance(value, int):
                parsed_number = value
            elif isinstance(value, str):
                try:
                    parsed_number = int(value.strip())
                except ValueError as error:
                    raise SettingsValidationError(f"{self.label} must be a whole number") from error
            else:
                raise SettingsValidationError(f"{self.label} must be a whole number")
            if self.minimum is not None and parsed_number < self.minimum:
                raise SettingsValidationError(f"{self.label} must be at least {int(self.minimum)}")
            if self.maximum is not None and parsed_number > self.maximum:
                raise SettingsValidationError(f"{self.label} must be at most {int(self.maximum)}")
            return parsed_number

        if self.value_type == "number":
            if isinstance(value, int | float):
                parsed_float = float(value)
            elif isinstance(value, str):
                normalized = value.strip().replace(",", ".")
                try:
                    parsed_float = float(normalized)
                except ValueError as error:
                    raise SettingsValidationError(f"{self.label} must be a number") from error
            else:
                raise SettingsValidationError(f"{self.label} must be a number")
            if not math.isfinite(parsed_float):
                raise SettingsValidationError(f"{self.label} must be a finite number")
            if self.minimum is not None:
                below_minimum = (
                    parsed_float < self.minimum
                    if self.minimum_inclusive
                    else parsed_float <= self.minimum
                )
                if below_minimum:
                    comparison = "at least" if self.minimum_inclusive else "greater than"
                    raise SettingsValidationError(
                        f"{self.label} must be {comparison} {self.minimum:g}"
                    )
            if self.maximum is not None and parsed_float > self.maximum:
                raise SettingsValidationError(f"{self.label} must be at most {self.maximum:g}")
            return parsed_float

        raise RuntimeError(f"unsupported field type: {self.value_type}")

    @property
    def choice_help_pt(self) -> dict[str, str]:
        return dict(self.choice_descriptions_pt)


_TEXT_NONEMPTY = (
    "texto não vazio, com até 100 caracteres (limite deste projeto). "
    "A Pocketpair não publica limite próprio."
)
_TEXT_OPTIONAL = (
    "texto, inclusive vazio, com até 500 caracteres (limite deste projeto). "
    "A Pocketpair não publica limite próprio."
)
_POSITIVE_RATE = (
    "número decimal maior que 0 (ponto ou vírgula). A Pocketpair não publica faixa nem máximo."
)
_RATE_MENU = "Decimal maior que 0; a Pocketpair não publica faixa máxima."


FIELDS: tuple[SettingField, ...] = (
    SettingField(
        "server_name",
        "ServerName",
        "Server name",
        "Nome do servidor",
        "Server",
        "string",
        _TEXT_NONEMPTY,
        "Texto não vazio, até 100 caracteres; sem limite oficial.",
        "Nome exibido pelo servidor.",
        max_length=100,
    ),
    SettingField(
        "server_description",
        "ServerDescription",
        "Server description",
        "Descrição do servidor",
        "Server",
        "string",
        _TEXT_OPTIONAL,
        "Texto ou vazio, até 500 caracteres; sem limite oficial.",
        "Descrição exibida pelo servidor.",
        max_length=500,
        allow_empty=True,
    ),
    SettingField(
        "max_players",
        "ServerPlayerMaxNum",
        "Maximum players",
        "Máximo de jogadores",
        "Server",
        "integer",
        "número inteiro maior ou igual a 1. A Pocketpair não publica valor máximo.",
        "Inteiro ≥ 1; a Pocketpair não publica máximo.",
        "Número máximo de jogadores que podem entrar.",
        minimum=1,
    ),
    SettingField(
        "base_camp_worker_max_num",
        "BaseCampWorkerMaxNum",
        "Maximum base workers",
        "Pals trabalhadores por base",
        "Base and Palbox",
        "integer",
        "número inteiro entre 1 e 50. Valores altos aumentam a carga do servidor.",
        "Inteiro de 1 a 50; valores altos aumentam a carga.",
        "Número máximo de Pals trabalhadores por base; o máximo oficial é 50.",
        minimum=1,
        maximum=50,
    ),
    SettingField(
        "allow_global_palbox_export",
        "bAllowGlobalPalboxExport",
        "Allow Global Palbox export",
        "Exportar para a Palbox Global",
        "Base and Palbox",
        "boolean",
        "True (permitir) ou False (bloquear).",
        "True permite salvar; False bloqueia.",
        "Permite salvar Pals na Palbox Global.",
        choices=("True", "False"),
        choice_descriptions_pt=(("True", "Permitir."), ("False", "Bloquear.")),
    ),
    SettingField(
        "allow_global_palbox_import",
        "bAllowGlobalPalboxImport",
        "Allow Global Palbox import",
        "Importar da Palbox Global",
        "Base and Palbox",
        "boolean",
        "True (permitir) ou False (bloquear).",
        "True permite carregar; False bloqueia.",
        "Permite carregar Pals da Palbox Global.",
        choices=("True", "False"),
        choice_descriptions_pt=(("True", "Permitir."), ("False", "Bloquear.")),
    ),
    SettingField(
        "exp_rate",
        "ExpRate",
        "Experience rate",
        "Taxa de experiência",
        "Gameplay",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de experiência recebida.",
        minimum=0,
    ),
    SettingField(
        "collection_drop_rate",
        "CollectionDropRate",
        "Collection drop rate",
        "Taxa de coleta",
        "Gameplay",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de itens coletáveis.",
        minimum=0,
    ),
    SettingField(
        "enemy_drop_item_rate",
        "EnemyDropItemRate",
        "Enemy drop item rate",
        "Drops de inimigos/Pals",
        "Gameplay",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador da quantidade de itens derrubados por inimigos e Pals derrotados.",
        minimum=0,
    ),
    SettingField(
        "pal_spawn_rate",
        "PalSpawnNumRate",
        "Pal spawn rate",
        "Taxa de spawn de Pals",
        "Gameplay",
        "number",
        _POSITIVE_RATE + " Valores altos podem afetar o desempenho.",
        "Decimal > 0; valores altos afetam desempenho.",
        "Multiplicador de spawn de Pals; pode afetar o desempenho.",
        minimum=0,
    ),
    SettingField(
        "death_penalty",
        "DeathPenalty",
        "Death penalty",
        "Penalidade de morte",
        "Gameplay",
        "choice",
        "None, Item, ItemAndEquipment ou All.",
        "None, Item, ItemAndEquipment ou All.",
        "Define o que o jogador perde ao morrer.",
        choices=("None", "Item", "ItemAndEquipment", "All"),
        choice_descriptions_pt=(
            ("None", "Não derruba nada."),
            ("Item", "Derruba itens, exceto equipamentos."),
            ("ItemAndEquipment", "Derruba itens e equipamentos."),
            ("All", "Derruba itens, equipamentos e Pals da equipe."),
        ),
    ),
    SettingField(
        "pal_auto_hp_regen_rate_in_sleep",
        "PalAutoHpRegeneRateInSleep",
        "Pal HP regeneration in Palbox",
        "Regeneração de HP na Palbox",
        "Gameplay",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de regeneração de HP dos Pals enquanto descansam na Palbox.",
        minimum=0,
    ),
    SettingField(
        "pal_egg_default_hatching_time",
        "PalEggDefaultHatchingTime",
        "Huge Egg hatching time",
        "Tempo de incubação dos ovos",
        "Gameplay",
        "number",
        "número decimal maior ou igual a 0, em horas; 0 torna a incubação instantânea.",
        "Horas ≥ 0; 0 torna a incubação instantânea.",
        "Tempo, em horas, para incubar um Ovo Enorme; os outros ovos também levam tempo.",
        minimum=0,
        minimum_inclusive=True,
    ),
    SettingField(
        "pal_damage_attack_rate",
        "PalDamageRateAttack",
        "Pal attack damage rate",
        "Dano causado por Pals",
        "Damage",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de dano causado por Pals.",
        minimum=0,
    ),
    SettingField(
        "pal_damage_defense_rate",
        "PalDamageRateDefense",
        "Pal received damage rate",
        "Dano recebido por Pals",
        "Damage",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de dano recebido por Pals.",
        minimum=0,
    ),
    SettingField(
        "player_damage_attack_rate",
        "PlayerDamageRateAttack",
        "Player attack damage rate",
        "Dano causado por jogadores",
        "Damage",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de dano causado por jogadores.",
        minimum=0,
    ),
    SettingField(
        "player_damage_defense_rate",
        "PlayerDamageRateDefense",
        "Player received damage rate",
        "Dano recebido por jogadores",
        "Damage",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de dano recebido por jogadores.",
        minimum=0,
    ),
    SettingField(
        "pal_stamina_decrease_rate",
        "PalStaminaDecreaceRate",
        "Pal stamina depletion rate",
        "Consumo de stamina dos Pals",
        "Stamina and inventory",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de consumo de stamina dos Pals.",
        minimum=0,
    ),
    SettingField(
        "player_stamina_decrease_rate",
        "PlayerStaminaDecreaceRate",
        "Player stamina depletion rate",
        "Consumo de stamina dos jogadores",
        "Stamina and inventory",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador de consumo de stamina dos jogadores.",
        minimum=0,
    ),
    SettingField(
        "item_weight_rate",
        "ItemWeightRate",
        "Item weight rate",
        "Peso dos itens",
        "Stamina and inventory",
        "number",
        _POSITIVE_RATE,
        _RATE_MENU,
        "Multiplicador do peso dos itens.",
        minimum=0,
    ),
)
FIELDS_BY_KEY = {field.key: field for field in FIELDS}
SECTIONS = tuple(dict.fromkeys(field.section for field in FIELDS))


def normalize_settings(
    raw_settings: object,
    *,
    require_all: bool = True,
    allow_extra: bool = False,
) -> dict[str, str | int | float | bool]:
    if not isinstance(raw_settings, dict):
        raise SettingsValidationError("settings must be a JSON object")

    expected = set(FIELDS_BY_KEY)
    actual = set(raw_settings)
    missing = sorted(expected - actual)
    if require_all and missing:
        raise SettingsValidationError(f"missing settings: {', '.join(missing)}")
    extra = sorted(actual - expected)
    if extra and not allow_extra:
        raise SettingsValidationError(f"unknown settings: {', '.join(extra)}")

    return {
        field.key: field.parse(raw_settings[field.key])
        for field in FIELDS
        if field.key in raw_settings
    }
