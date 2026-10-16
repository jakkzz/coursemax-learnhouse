# Class task color roles

The `/classes` color pass preserves LearnHouse's existing light workspace, account
shell, typography and weekday category colors. It changes neither copy nor workflow,
permissions, source data, theme settings or backend code.

`class-colors.module.css` scopes native control-role overrides to class tasks:

| Role | Foreground | Surface |
| --- | --- | --- |
| Primary action | `#ffffff` | `#1d4ed8` |
| Information / selection | `#1e40af` | `#eff6ff` |
| Pending course match / repair | `#92400e` | `#fffbeb` |
| Connected class / reading access | `#166534` | `#f0fdf4` |
| Failure / conflicting connection | `#991b1b` | `#fef2f2` |
| Ordinary unmatched account | `#525252` | `#f5f5f5` |

Blue follows the existing School workspace. Color primarily identifies actions,
selection and actionable state; it is not decorative course categorization. The
strongest blue belongs to the primary task. Connected and pending sections receive
quiet status surfaces, and roster account matches receive compact text labels.
Unmatched accounts remain neutral rather than making an ordinary roster look like
an alert. Existing labels remain, Lucide icons reinforce state, and selected task
navigation has an underline as a non-color cue.

Native button interaction/disabled behavior is reused. Selection, caret and focus
remain blue, reduced-motion preferences are respected and forced-colors retains
system-visible boundaries. No global stylesheet or native component is modified.

Checks: source tests calculate AA text contrast under ordinary vision and linear
protanopia/deuteranopia/tritanopia simulations. Rendered checks must also inspect
computed native primary-button colors, status foreground/surface pairs, keyboard
selection and desktop/mobile English/Thai task completion. Simulations are checks,
not a claim that color alone can convey state.

See [section workflow](class-section-setup.md) and the existing root `DESIGN.md` for
the incumbent visual world. This owned note does not redefine the global design.
