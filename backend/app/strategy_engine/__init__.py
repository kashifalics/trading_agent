"""Strategy engine v2 (docs/engine_v2/DESIGN.md): regime classifier, six independent strategies, selector, trade-plan builder,
risk, sessions and the signal lifecycle. Every threshold is a frozen, pre-registered hypothesis (docs/engine_v2/EXPERIMENT_PLAN.md);
no strategy here is validated. v1 (app.signals) is unchanged and keeps feeding the paper forward test."""
