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


def test_every_guardrail_resource_is_gated_on_the_enable_flag():
    # Aucun garde-fou ne s'instancie sans stratus_guardrails_enabled. Le terraform_data
    # stratus_guard est à part : il porte la precondition et existe toujours (inerte), mais sa
    # condition passe trivialement quand le flag est faux.
    for m in re.finditer(r'^(resource|data)\s+"([^"]+)"', _GUARDRAILS, re.MULTILINE):
        if m.group(2) == "terraform_data":
            continue
        header = _GUARDRAILS[m.start() : _GUARDRAILS.index("{", m.start())].strip()
        block = _block(_GUARDRAILS, header)
        assert "var.stratus_guardrails_enabled" in block, f"ressource non gardée : {block[:80]}"


# ── Le refus de viser le mauvais abonnement — une precondition, pas un check ─────────────────


def test_a_precondition_refuses_pointing_at_orodruins_own_subscription():
    # En Terraform un `check` raté n'est qu'un avertissement : le refus est une `precondition`
    # sur terraform_data.stratus_guard, dont dépendent les garde-fous — un plan qui vise le
    # mauvais abonnement échoue avant de rien poser.
    block = _block(_GUARDRAILS, 'resource "terraform_data" "stratus_guard"')
    assert "precondition" in block
    # La cible, comparée À l'abonnement d'Orodruin, doit DIFFÉRER (!=). On vise la comparaison
    # elle-même, pas un `!=` quelconque (le `!= ""` du contrôle de renseignement en est un autre).
    assert "!= lower(data.azurerm_subscription.current.subscription_id)" in block
    # activé ⇒ cible renseignée
    assert 'var.stratus_subscription_id != ""' in block


def test_the_guardrails_depend_on_the_guard():
    # Chaque ressource de l'abonnement dédié file l'abonnement validé par la garde
    # (terraform_data.stratus_guard.output), ou en dépend ; aucune ne lit var.stratus_subscription_id
    # en direct pour sa cible d'abonnement.
    assert "terraform_data.stratus_guard.output" in _GUARDRAILS
    assert "/subscriptions/${var.stratus_subscription_id}" not in _GUARDRAILS


def test_the_alias_provider_targets_the_dedicated_subscription():
    # Le seul bloc provider "azurerm" du fichier est l'alias stratus (le défaut est dans main.tf).
    block = _block(_GUARDRAILS, 'provider "azurerm"')
    assert re.search(r'alias\s*=\s*"stratus"', block)
    assert "var.stratus_subscription_id" in block
    # jamais repointé sur l'abonnement d'Orodruin (var.subscription_id)
    assert "var.subscription_id" not in block


def test_every_dedicated_subscription_resource_declares_the_stratus_provider():
    # Chaque ressource de l'abonnement dédié passe par l'alias ; le groupe d'action du budget
    # (abonnement d'Orodruin) ne doit PAS ; le garde-fou terraform_data est à part.
    for m in re.finditer(r'^resource\s+"([^"]+)"\s+"([^"]+)"', _GUARDRAILS, re.MULTILINE):
        rtype, rname = m.group(1), m.group(2)
        block = _block(_GUARDRAILS, f'resource "{rtype}" "{rname}"')
        if rtype == "azurerm_monitor_action_group":
            assert "azurerm.stratus" not in block, f"{rname} ne doit pas viser l'abonnement dédié"
        elif rtype == "terraform_data":
            continue
        else:
            assert "azurerm.stratus" in block, f"{rname} doit déclarer provider = azurerm.stratus"


# ── G5 — la Policy ──────────────────────────────────────────────────────────────────────────


def test_a_custom_policy_denies_a_public_ip_on_a_nic():
    block = _block(_GUARDRAILS, 'resource "azurerm_policy_definition" "stratus_deny_nic_public_ip"')
    assert "Microsoft.Network/networkInterfaces" in block
    assert "publicIPAddress" in block
    assert '"deny"' in block or "effect = \"deny\"" in block


def test_the_nic_public_ip_policy_matches_any_ip_config():
    block = _block(_GUARDRAILS, 'resource "azurerm_policy_definition" "stratus_deny_nic_public_ip"')
    # « au moins une » ipConfig avec une IP publique = not{ … notLike = "*" }, pas le [*]…exists
    # naïf qu'une NIC mixte (une ipConfig sans IP publique, une avec) contournerait. On vise
    # l'attribut (notLike = "*"), pas un « notLike » quelconque (le commentaire en contient un).
    assert re.search(r'notLike\s*=\s*"\*"', block)
    assert 'exists = "true"' not in block
    # l'enveloppe `not { … }` : sans elle la policy est inversée (refuserait une NIC privée,
    # laisserait passer une NIC 100 % IP publique). Le run Terraform l'asserte sur la règle décodée.
    assert re.search(r"not\s*=\s*\{", block)


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
    # cible = l'abonnement dédié tout entier (l'abonnement validé par la garde), pas le banc
    assert "/subscriptions/${terraform_data.stratus_guard.output}" in block


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
    assert "/subscriptions/${terraform_data.stratus_guard.output}" in block
    assert "azurerm_monitor_action_group.stratus_budget[0].id" in block


def test_the_subscription_id_is_validated_as_a_guid():
    # Un GUID nu, jamais la forme chemin /subscriptions/<guid> : sinon l'abonnement d'Orodruin
    # en forme chemin contournerait la precondition (comparaison de chaînes brutes).
    block = _block(_VARIABLES, 'variable "stratus_subscription_id"')
    assert "validation" in block
    assert "[0-9a-fA-F]{12}" in block


def test_every_dedicated_subscription_resource_depends_on_the_guard():
    # Chaque ressource de l'abonnement dédié dépend de terraform_data.stratus_guard (elle file
    # l'abonnement validé par sa sortie, ou un depends_on explicite) : un plan qui vise le mauvais
    # abonnement échoue avant de rien poser. Le groupe d'action (abonnement d'Orodruin) et le
    # garde-fou lui-même sont à part.
    for m in re.finditer(r'^resource\s+"([^"]+)"\s+"([^"]+)"', _GUARDRAILS, re.MULTILINE):
        rtype, rname = m.group(1), m.group(2)
        if rtype in ("azurerm_monitor_action_group", "terraform_data"):
            continue
        block = _block(_GUARDRAILS, f'resource "{rtype}" "{rname}"')
        assert "terraform_data.stratus_guard" in block, f"{rname} ne dépend pas de la garde"


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
