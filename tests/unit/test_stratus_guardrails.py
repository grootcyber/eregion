"""R2b (#608) — les garde-fous de l'abonnement de test dédié de Stratus, lus dans le Terraform.

On lit infra/orodruin/stratus_guardrails.tf et variables.tf comme texte (comme
test_orodruin.py lit main.tf) : pas d'apply, pas de credential. Ce qui compte, invariant par
invariant (docs/design/stratus-cible.md, § 6) :

- tout est ÉTEINT par défaut (un apply normal d'Orodruin n'y touche pas) ;
- le paramètre de diagnostic route la seule catégorie Administrative vers le workspace du banc ;
- le groupe d'action du budget vit HORS de l'abonnement dédié (pas le fournisseur stratus) ;
- un refus maison d'une IP publique sur une carte réseau ;
- les listes « autorisées » vides ne posent rien (une liste vide refuserait tout) ;
- le rôle fermé de Stratus (G3) n'est PAS encore écrit ici (il attend la mesure M1).
"""

import re
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "infra" / "orodruin"
_GUARDRAILS = (_MODULE / "stratus_guardrails.tf").read_text(encoding="utf-8")
_VARIABLES = (_MODULE / "variables.tf").read_text(encoding="utf-8")
_OUTPUTS = (_MODULE / "outputs.tf").read_text(encoding="utf-8")


def _block(source: str, header: str) -> str:
    """Le corps d'un bloc HCL `resource/provider/check "<header>"` — accolades équilibrées."""
    start = source.index(header)
    depth = 0
    opened = False
    for i in range(start, len(source)):
        c = source[i]
        if c == "{":
            depth += 1
            opened = True
        elif c == "}":
            depth -= 1
            if opened and depth == 0:
                return source[start : i + 1]
    raise AssertionError(f"bloc non terminé : {header}")


def _var_default(name: str) -> str:
    """La valeur `default` d'une variable, telle qu'écrite."""
    block = _block(_VARIABLES, f'variable "{name}"')
    m = re.search(r"default\s*=\s*(.+)", block)
    assert m, f"{name} n'a pas de default"
    return m.group(1).strip()


# ── Éteint par défaut ───────────────────────────────────────────────────────────────────────


def test_the_guardrails_are_off_by_default():
    assert _var_default("stratus_guardrails_enabled") == "false"


def test_the_dedicated_subscription_is_empty_by_default():
    assert _var_default("stratus_subscription_id") == '""'


def test_the_allow_lists_and_budget_are_empty_by_default():
    assert _var_default("stratus_allowed_locations") == "[]"
    assert _var_default("stratus_allowed_resource_types") == "[]"
    assert _var_default("stratus_allowed_vm_skus") == "[]"
    assert _var_default("stratus_bench_workspace_id") == '""'
    assert _var_default("stratus_monthly_budget") == "0"
    assert _var_default("stratus_budget_start_date") == '""'


def test_every_resource_is_gated_on_the_enable_flag():
    # Aucune ressource ni data du fichier ne s'instancie sans stratus_guardrails_enabled.
    for m in re.finditer(r'^(resource|data)\s+"', _GUARDRAILS, re.MULTILINE):
        block = _block(_GUARDRAILS, _GUARDRAILS[m.start() : _GUARDRAILS.index("{", m.start())].strip())
        assert "var.stratus_guardrails_enabled" in block, f"ressource non gardée : {block[:80]}"


# ── Le refus de viser le mauvais abonnement ─────────────────────────────────────────────────


def test_a_check_refuses_pointing_at_orodruins_own_subscription():
    block = _block(_GUARDRAILS, 'check "stratus_subscription_is_dedicated"')
    # La cible, comparée À l'abonnement d'Orodruin, doit DIFFÉRER (!=). On vise la comparaison
    # elle-même, pas un `!=` quelconque (le `!= ""` du contrôle de renseignement en est un autre).
    assert "!= lower(data.azurerm_subscription.current.subscription_id)" in block
    # activé ⇒ cible renseignée
    assert 'var.stratus_subscription_id != ""' in block


# ── G5 — la Policy ──────────────────────────────────────────────────────────────────────────


def test_a_custom_policy_denies_a_public_ip_on_a_nic():
    block = _block(_GUARDRAILS, 'resource "azurerm_policy_definition" "stratus_deny_nic_public_ip"')
    assert "Microsoft.Network/networkInterfaces" in block
    assert "publicIPAddress" in block
    assert '"deny"' in block or "effect = \"deny\"" in block


def test_the_allow_list_policies_do_not_fire_on_an_empty_list():
    # Une liste vide en mode deny refuserait TOUTE création : la garde est le count.
    for name in (
        "stratus_allowed_locations",
        "stratus_allowed_resource_types",
        "stratus_allowed_vm_skus",
    ):
        block = _block(_GUARDRAILS, f'resource "azurerm_subscription_policy_assignment" "{name}"')
        assert f"length(var.{name}) > 0" in block


# ── G6 — le paramètre de diagnostic ─────────────────────────────────────────────────────────


def test_the_diagnostic_setting_routes_only_administrative_to_the_bench_workspace():
    block = _block(_GUARDRAILS, 'resource "azurerm_monitor_diagnostic_setting" "stratus_activity_log"')
    assert "provider" in block and "azurerm.stratus" in block
    # la seule catégorie, comme activity_log.tf du banc
    categories = re.findall(r"category\s*=\s*\"([^\"]+)\"", block)
    assert categories == ["Administrative"], categories
    assert "var.stratus_bench_workspace_id" in block
    # cible = l'abonnement dédié tout entier, pas le banc
    assert "/subscriptions/${var.stratus_subscription_id}" in block


# ── G7 — le budget, groupe d'action HORS de l'abonnement dédié ──────────────────────────────


def test_the_budget_action_group_lives_outside_the_dedicated_subscription():
    block = _block(_GUARDRAILS, 'resource "azurerm_monitor_action_group" "stratus_budget"')
    # dans le groupe d'Orodruin (fournisseur par défaut), jamais l'abonnement dédié :
    # sinon COLD/kill et « vider l'abonnement » l'emporteraient.
    assert "azurerm_resource_group.host.name" in block
    assert "azurerm.stratus" not in block


def test_the_budget_itself_is_on_the_dedicated_subscription_and_notifies_the_outside_group():
    block = _block(_GUARDRAILS, 'resource "azurerm_consumption_budget_subscription" "stratus"')
    assert "azurerm.stratus" in block
    assert "/subscriptions/${var.stratus_subscription_id}" in block
    assert "azurerm_monitor_action_group.stratus_budget[0].id" in block


# ── Le rôle fermé (G3) n'est PAS encore écrit ───────────────────────────────────────────────


def test_no_closed_role_is_granted_here_yet():
    # G3/G4 attendent la mesure M1 : aucune définition ni attribution de rôle dans ce fichier.
    assert "azurerm_role_definition" not in _GUARDRAILS
    assert "azurerm_role_assignment" not in _GUARDRAILS


# ── Les sorties ne fuient rien et restent nulles quand c'est éteint ─────────────────────────


def test_outputs_are_null_when_the_guardrails_are_off():
    for name in (
        "stratus_diagnostic_setting_id",
        "stratus_budget_action_group_id",
        "stratus_policy_assignment_ids",
    ):
        assert f'output "{name}"' in _OUTPUTS
