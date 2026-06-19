# Vriddhi Capital

Vriddhi Capital is a startup finance cockpit for Indian founders and finance teams. It brings revenue tracking, expense control, receivables, payables, GST invoicing, accountant exports, tax planning, role-based access, and automated invoice communication into one production-ready operating system.

The product is designed for SaaS, service, consulting, agency, and early-stage startup teams that need finance visibility without waiting for a full accounting department. A founder can see cash runway, GST exposure, overdue collections, budget burn, revenue mix, foreign-currency exposure, and reminder status from the main dashboard, while an accountant can still reach invoices, ledgers, payables, and exports when needed.

The product layer is implemented as a custom Frappe app on top of the open-source Frappe/ERPNext platform and India-compliance-compatible accounting workflows. Vriddhi Capital owns the curated dashboard, dense startup dataset, calculators, product navigation, notification audit logs, custom fields, user roles, operating workflows, and submission-facing experience.

## Product Modules

- **Founder cockpit:** live financial KPIs, cash runway, GST exposure, receivables, payables, tax estimate, overdue invoices, and dashboard period controls.
- **Income and invoicing:** GST sales invoice creation with client records, GSTIN, HSN/SAC, invoice numbering, status tracking, PDF generation, and IRN-style reference evidence.
- **Expense and payables:** vendor bills, category-tagged expenditure, input GST credit, payable aging, purchase invoice records, and payment workflows.
- **Receivables and reminders:** outstanding client invoices, due dates, overdue status, collection aging, reminder sequence, and notification trigger logs.
- **GST India workspace:** CGST/SGST/IGST evidence, GST composition chart, recent GST invoices, seeded HSN/SAC usage, and compliance proof panels.
- **Financial reports:** P&L-oriented dashboard views, ledgers, receivable/payable evidence, budget tracking, YoY/MoM trends, and accountant-ready exports.
- **Founder calculators:** GST liability, advance tax, runway/burn, DSO, budget variance, GST pricing, and FX impact calculators.
- **Integrations:** Email and Telegram invoice delivery/reminder triggers with visible delivery/audit logs and simulated fallback when live channels are unavailable.
- **Access control:** Founder, Accountant, Finance Viewer, and Vriddhi Judge roles with curated product navigation and blocked raw admin routes for judge-facing accounts.

## Tech Stack

- Backend: Frappe Framework 15, ERPNext 15, Python
- Database: MariaDB through Frappe/ERPNext DocTypes
- Frontend: Frappe Desk page, JavaScript, CSS
- Charts: Apache ECharts bundled locally in `public/js/echarts.min.js`
- Notifications: Frappe Email Account plus Telegram Bot API, with simulated audit-log fallback
- Deployment: Docker/bench production site on Ubuntu EC2

## Design Goals

- **Production-first:** persistent database records, real authentication, hosted deployment, seeded financial data, and working CRUD flows.
- **Founder-readable:** financial metrics are shown in business language instead of only accounting report language.
- **Accountant-compatible:** invoices, payment entries, ledgers, budgets, exports, and master data remain structured for finance review.
- **India-ready:** GST fields, HSN/SAC codes, tax split examples, GSTIN records, and invoice PDFs are built into the operating flow.
- **Submission-safe:** judge-facing users see a curated product shell with the important finance modules and no unrelated framework navigation.

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
All seeded role accounts are routed through the curated Vriddhi product shell; raw framework/admin routes are blocked from the judge-facing experience.

## Seeded Data

The seed creates realistic startup finance data across FY 2023-24, FY 2024-25, FY 2025-26, and FY 2026-27 YTD:

- GST sales invoices, purchase invoices, payment entries, receivables, payables, and GL entries
- Indian GST fields, HSN/SAC service items, CGST/SGST/IGST split examples, and IRN-style references
- Clients, vendors, contacts, billing addresses, GSTINs, and notification preferences
- Bank import rows with auto-categorization states
- Budget lines by category and fiscal year
- USD/EUR/AED client billing data plus currency exchange records
- Email/Telegram invoice delivery and reminder trigger logs

The dataset is intentionally dense enough for charts, filters, aging reports, category breakdowns, reminders, and exports to be visible immediately after login. Judges do not need to create records from scratch to understand the product.

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

## Future Scope

Vriddhi Capital is structured as a modular finance platform, so the next roadmap can expand without changing the core operating model:

- Domain email and branded sender identity for production invoice delivery.
- Deeper bank reconciliation with rule learning and statement-matching confidence.
- Founder-facing cash planning scenarios for hiring, marketing spend, runway, and funding events.
- GST return pack generation with accountant review workflow.
- Multi-company workspace for founders operating multiple startups under one login.
- Approval workflows for expenses, vendor payments, invoice write-offs, and budget overrides.
- Investor reporting pack with board-ready monthly metrics and exportable summaries.
- Optional WhatsApp Business integration alongside Telegram and Email.
- Deeper CRM-to-invoice flow for converting opportunities into proposals, invoices, and receivables.
- Production hardening with backups, domain TLS, monitoring, and a dedicated transactional email provider.

No submission zip is generated from this repo unless explicitly requested.
