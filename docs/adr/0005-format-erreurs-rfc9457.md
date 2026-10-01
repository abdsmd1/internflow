# 0005 — Format d'erreur RFC 9457 (Problem Details)

- **Statut :** Accepté
- **Date :** 2026-10-01

## Contexte

Le frontend et l'agent IA consomment l'API : ils doivent pouvoir traiter toutes
les erreurs de la même manière, et aucune information interne ne doit fuiter.

## Décision

Toutes les erreurs sont renvoyées en `application/problem+json` (RFC 9457) :

```json
{
  "type": "https://internflow.dev/problems/email-already-used",
  "title": "Conflict",
  "status": 409,
  "detail": "L'adresse sara@example.com est déjà utilisée par un autre stagiaire.",
  "instance": "/api/v1/interns"
}
```

- Les exceptions métier sont traduites en statuts HTTP **dans la couche présentation**
  (le domaine ignore HTTP).
- Les erreurs de validation ajoutent un champ `errors` détaillé.
- Les erreurs inattendues renvoient un message générique ; le détail part dans
  les logs, corrélé par `X-Request-ID`.

## Conséquences

- ✅ Le champ `type` est stable : l'agent IA peut réagir à une erreur précise.
- ✅ Aucune stack trace exposée.
