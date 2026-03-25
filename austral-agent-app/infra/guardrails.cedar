// Security Guardrail: Prevent the agent from making financial transactions
forbid(
    principal,
    action == AustralCrew::Action::"execute_payment",
    resource
);

// Permit tool usage for Solar and Fuel analysis
permit(
    principal == AustralCrew::Agent,
    action in [AustralCrew::Action::"get_solar_yield", AustralCrew::Action::"find_best_p98"],
    resource
);