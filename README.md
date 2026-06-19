# Vriddhi Capital

Vriddhi Capital is a startup finance cockpit for financial tracking, GST invoicing, receivables/payables, accountant exports, and automated invoice communication.

The product layer is implemented as a custom Frappe app on top of the open-source Frappe/ERPNext platform and India-compliance-compatible accounting workflows. Vriddhi Capital owns the curated dashboard, seeded operating data, calculators, navigation, notification audit logs, custom fields, roles, and submission-facing experience.

## Tech Stack

- Backend: Frappe Framework 15, ERPNext 15, Python
- Database: MariaDB through Frappe/ERPNext DocTypes
- Frontend: Frappe Desk page, JavaScript, CSS
- Charts: Apache ECharts bundled locally in `public/js/echarts.min.js`
- Notifications: Frappe Email Account plus Telegram Bot API, with simulated audit-log fallback
- Deployment: Docker/bench production site on Ubuntu EC2

## Setup

Install the app into a configured Frappe/ERPNext bench/site, migrate, build assets, then seed the dataset:

```bash
bench --site your-site-name install-app vriddhi_capital
bench --site your-site-name migrate
bench --site your-site-name build --app vriddhi_capital
bench --site your-site-name seed-vriddhi
```

The seed command is idempotent. Running it again should not duplicate existing invoices, bank rows, budgets, or notification evidence.

## Environment / Site Config

Do not commit real secrets. Configure them in the site config or host secret manager:

```bash
bench --site your-site-name set-config telegram_bot_token "TELEGRAM_BOT_TOKEN"
bench --site your-site-name set-config telegram_default_chat_id "TELEGRAM_CHAT_ID"
```

SMTP should be configured through Frappe Email Account. If Email or Telegram is not configured, Vriddhi Capital writes clearly labeled simulated trigger logs in `Notification Trigger Log`.

## Sample Logins

Seeded users use this password unless changed after deployment:

```text
founder@vriddhi.local      / Vriddhi@2026
accountant@vriddhi.local   / Vriddhi@2026
viewer@vriddhi.local       / Vriddhi@2026
judge@vriddhi.local        / Vriddhi@2026
```

Admin credentials should be provided separately by the deployment owner.

## Seeded Data

The seed creates realistic startup finance data across FY 2023-24, FY 2024-25, FY 2025-26, and FY 2026-27 YTD:

- GST sales invoices, purchase invoices, payment entries, receivables, payables, and GL entries
- Indian GST fields, HSN/SAC service items, CGST/SGST/IGST split examples, and IRN-style references
- Clients, vendors, contacts, billing addresses, GSTINs, and notification preferences
- Bank import rows with auto-categorization states
- Budget lines by category and fiscal year
- USD/EUR/AED client billing data plus currency exchange records
- Email/Telegram invoice delivery and reminder trigger logs

## Feature Checklist

### Must-Have

1. Income/revenue entry: `Record Income` creates GST Sales Invoices.
2. Expenditure entry: `Record Expense` creates Purchase Invoices with category/vendor evidence.
3. Receivables tracker: dashboard aging, receivables table, Accounts Receivable report link.
4. Payables tracker: payable aging, upcoming payables table, Accounts Payable report link.
5. Profit and Loss: net profit card and P&L report link.
6. Category reports: income mix, spend mix, budget variance and tables.
7. GST invoice generation: GSTIN/address, HSN/SAC, CGST/SGST/IGST, invoice numbering and IRN-style field.
8. Invoice PDF: PDF action on recent GST invoices.
9. Invoice status tracking: Draft/Sent/Paid/Partially Paid/Overdue sync field.
10. Client/vendor masters: Customer and Supplier records with contact, GSTIN, address and billing settings.
11. Invoice delivery trigger: Email/Telegram hooks and trigger log fallback.
12. Payment reminder trigger: Run Reminder Sequence and daily scheduler fallback.
13. Recurring invoices: Auto Repeat record seeded and linked.
14. Dashboard metrics: revenue, expenses, net profit, cash, GST, receivables, payables, tax estimate.
15. Central admin panel: curated Vriddhi dashboard, master links, operational tables, ledger CSV and Tally CSV exports.

### Good-To-Have

1. Bank CSV import: `Import Bank CSV` plus Bank Import Entry records.
2. Multi-user roles: Founder, Accountant, Finance Viewer, Vriddhi Judge.
3. Tax calculators: GST, advance tax, runway, DSO, budget, pricing and FX calculators.
4. Receipt upload: Purchase Invoice receipt attachment field.
5. Budget vs actual: budget lines and actual vendor spend chart.
6. Multi-currency: USD/EUR/AED client invoices, exchange rates, and currency exposure chart.
7. Simulated IRN: `IRN-style Reference` custom field.
8. Late reminder sequence: reminder count, reminder days and trigger logs.
9. YoY/MoM charts: 4-year growth plus MoM/YoY comparison charts.
10. Accountant exports: full ledger CSV and Tally-style voucher CSV.

## Judge-Facing Routes

- Main app: `/app/vriddhi-capital`
- Calculators: `/app/vriddhi-capital?view=calculators`
- Account profile: `/app/vriddhi-capital?view=profile`
- Notification logs: `/app/notification-trigger-log`

No submission zip is generated from this repo unless explicitly requested.
