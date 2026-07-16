# SoftSystem97 — App Frappe

Application ERPNext pour le portail client SoftSystem97 : webhooks Stripe, notifications, KPIs finance et workflow contrats.

## Prérequis

- Bench Frappe v14+ / v15+ avec **ERPNext** installé
- Python 3.10+
- Accès SSH ou console Frappe Cloud (bench privé)

## Installation (Frappe Cloud — bench privé)

### 1. Ajouter l'app au bench

```bash
cd ~/frappe-bench
bench get-app https://github.com/softsystem97/softsystem97.git
# ou depuis un chemin local / artefact CI :
bench get-app /path/to/softsystem97
```

### 2. Installer sur le site

```bash
bench --site <votre-site> install-app softsystem97
bench --site <votre-site> migrate
```

### 3. Configuration Stripe (sans secrets dans le code)

**Option A — `site_config.json` (recommandé Frappe Cloud)**

```json
{
  "STRIPE_MODE": "test",
  "PAYMENTS_LIVE_ENABLED": 0,
  "STRIPE_TEST_WEBHOOK_SECRET": "whsec_...",
  "STRIPE_WEBHOOK_SECRET": "whsec_..."
}
```

**Option B — DocType `SS97 Stripe Config` (Single)**

Renseigner les champs Password :

| Champ | Usage |
|-------|--------|
| `test_webhook_secret` | Webhook Stripe mode TEST |
| `webhook_secret` | Webhook Stripe mode LIVE |
| `test_secret_key` / `live_secret_key` | Clés API (checkout côté site) |
| `payments_live_enabled` | `0` = rejeter les événements `livemode: true` |

> Ne jamais committer de secrets. Les valeurs Password ne sont jamais loguées par l'app.

### 4. Enforcer le mode TEST

Tant que `PAYMENTS_LIVE_ENABLED` est `0` (ou absent/falsy), seuls les événements Stripe avec `livemode: false` sont acceptés.

## Webhook Stripe

### URL endpoint

```
POST https://<votre-site>/api/method/softsystem97.integrations.stripe.webhook.stripe_webhook
```

Alias équivalent :

```
POST https://<votre-site>/api/method/softsystem97.integrations.stripe.webhook.webhook
```

### Enregistrement dans Stripe Dashboard

1. **Developers → Webhooks → Add endpoint**
2. Coller l'URL ci-dessus
3. Sélectionner les événements :

| Événement | Action ERP |
|-----------|------------|
| `checkout.session.completed` | Paiement checkout → Payment Entry + champs `ss97_*` |
| `payment_intent.succeeded` | Paiement confirmé |
| `payment_intent.payment_failed` | Échec paiement + notification client |
| `invoice.paid` | Facture Stripe payée |
| `invoice.payment_failed` | Échec facture récurrente |
| `customer.subscription.created` | Abonnement créé |
| `customer.subscription.updated` | Abonnement mis à jour |
| `customer.subscription.deleted` | Abonnement supprimé |
| `charge.refunded` | Remboursement |

4. Copier le **Signing secret** (`whsec_...`) dans `STRIPE_TEST_WEBHOOK_SECRET` ou `SS97 Stripe Config.test_webhook_secret`

### Sécurité webhook

- Vérification signature header `Stripe-Signature` (HMAC SHA-256)
- Rejet si timestamp > 5 minutes (anti-replay)
- Idempotence via DocType `SS97 Stripe Event` (événement `Success` = pas de retraitement)
- HTTP 403 si signature invalide ou mode LIVE bloqué

## APIs portail (authentification requise)

Toutes les APIs portail filtrent strictement par `frappe.session.user`. Un staff sans lien Customer reçoit des listes vides (sauf param `customer` pour System Manager / Accounts Manager).

| Méthode | Description |
|---------|-------------|
| `softsystem97.portal.notifications.get_my_notifications` | Liste notifications |
| `softsystem97.portal.notifications.mark_read` | Marquer lue |
| `softsystem97.portal.notifications.mark_all_read` | Tout marquer lu |
| `softsystem97.portal.notifications.delete_notification` | Supprimer (SS97 Client Notification) |
| `softsystem97.portal.finance.get_my_finance_kpis` | KPIs finance client |
| `softsystem97.portal.finance.get_my_invoices` | Factures client |
| `softsystem97.portal.finance.get_my_contracts` | Contrats client |
| `softsystem97.portal.finance.get_my_quotations` | Devis client |
| `softsystem97.portal.contracts.list_my_contracts` | Liste contrats |
| `softsystem97.portal.contracts.get_contract` | Détail (+ passage Envoyé → Consulté) |
| `softsystem97.portal.contracts.sign_contract` | Signature |
| `softsystem97.portal.contracts.refuse_contract` | Refus |
| `softsystem97.portal.contracts.request_modification` | Demande modification |

## DocTypes fournis

| DocType | Rôle |
|---------|------|
| `SS97 Stripe Event` | Journal idempotent des webhooks |
| `SS97 Client Notification` | Notifications portail dédiées |
| `SS97 Stripe Config` | Configuration Single (clés Password) |

## Champs custom attendus (ERPNext natif)

L'app utilise en best-effort les champs custom suivants s'ils existent sur `Sales Invoice` / `Contract` / `Customer` :

- `ss97_stripe_session_id`, `ss97_stripe_payment_intent`, `ss97_payment_status`
- `ss97_receipt_ref`, `ss97_stripe_mode`, `ss97_paid_on`
- `ss97_contract_status`, `ss97_signed_on`, etc.

## Développement local

```bash
cd ~/frappe-bench
bench start
# après modification Python :
bench --site <site> migrate
```

## Licence

MIT — SoftSystem97
