{
    "name": "Employee Self Service (ESS)",
    "summary": "Secure employee self-service portal",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "license": "LGPL-3",
    "author": "Employee Self Service",
    "depends": ["hr", "mail", "web"],
    "data": [
        "security/ess_groups.xml",
        "security/ir.model.access.csv",
        "security/ess_rules.xml",
        "views/ess_views.xml",
        "data/ess_cron.xml",
    ],
    "application": True,
    "installable": True,
}
