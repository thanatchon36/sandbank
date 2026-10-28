# Responsible use

SandBank is a research instrument for measuring whether LLM agents keep to KYC/AML controls when a
business target pushes against them. It is released so that others can check the study's result and test
their own agents before deployment.

## Intended use

- Measuring an agent's propensity to circumvent controls, and what it does instead, under pressure.
- Pricing guardrails: how much legitimate work a mitigation costs when the agent is already compliant.
- Replicating or extending the pre-registered study (`PREREGISTRATION.md`, `DEVIATIONS.md`).

## Not intended

- Training, fine-tuning or selecting agents for their ability to evade compliance controls.
- Using the circumvention paths as guidance for evading real banking controls. They are the generic paths
  that any override field allows, and they are described here only by violation type.
- Treating a clean SandBank result as certification of an agent for production. The sandbox has one
  fictional bank, one clear policy and short episodes; a real deployment needs its own testing, logging and
  hard controls on prohibited actions.

## Data

Everything is synthetic: the Republic of Meridia, the Meridian Financial Authority, SandBank, its customers,
documents, sanctions list and money are fictional. Names are generated with `Faker` from fixed seeds; any
resemblance to a real person is coincidental. No real institution's systems, data or policies are used.

## Reporting

If you find a way in which the sandbox or detector could cause harm, or a result that contradicts the
paper, please open an issue on the repository.
