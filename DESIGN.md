# EdgeErgo V3 — Design Document

**Version:** 1.0  
**Status:** Visual and interaction specification  
**Reference:** User-provided dark analytics dashboard image  
**Product:** EdgeErgo — Privacy-Preserving Ergonomic Assessment  
**Applies to:** React web dashboard; complements the Windows desktop agent UI  
**Related documents:** `PRD.md`, `TECH_STACK.md`

---

## 1. Design Direction

EdgeErgo uses a polished, dark analytics-dashboard style inspired by the supplied reference image: near-black canvas, layered charcoal panels, restrained borders, rounded cards, clear data visualization, and a violet accent for primary actions and selected states.

The reference image is a visual direction, not a source of EdgeErgo product features or data. EdgeErgo must present ergonomic assessment information—not marketing analytics. All metrics must come from real API/database responses, and unavailable data must be clearly identified rather than fabricated.

### Design goals

- Make ergonomic status and recent trends understandable at a glance.
- Give the dashboard a modern, high-quality visual finish without visual clutter.
- Make privacy, device connectivity, and data freshness visible.
- Use non-punitive language focused on practical adjustments and breaks.
- Keep navigation and interaction patterns consistent across pages.
- Work well on desktop, tablet, and mobile widths.
- Preserve keyboard access, readable contrast, and chart summaries.

### Experience principles

1. **Inform, don't judge:** Do not rank workers or frame scores as employee performance.
2. **Show uncertainty:** Indicate when observations are invalid, insufficient, or unavailable.
3. **Make privacy visible:** State that camera analysis happens on the workstation and only approved summaries synchronize.
4. **Use real data:** Do not display demo values as live data.
5. **Prefer actionable feedback:** Recommendations should connect to observed posture indicators and be phrased neutrally.
6. **Progressive detail:** The overview gives a summary; assessment details and reports provide supporting context.

---

## 2. Visual Identity

### Overall appearance

- Dark-first interface.
- Deep black page background with slightly lighter charcoal surfaces.
- Subtle one-pixel borders and restrained shadows.
- Rounded panels with consistent corner radii.
- White and soft-gray text, with muted gray for secondary labels.
- Violet as the primary accent; green, amber, and red are reserved for meaningful status or severity and must never be the only way information is communicated.
- Thin, quiet chart gridlines and restrained chart fills.
- Avoid excessive gradients, glow effects, and decorative animation. Use a small violet gradient only for primary emphasis or an optional insight card.

### Suggested color tokens

| Token | Suggested value | Usage |
|---|---|---|
| `--bg` | `#08090B` | Main application background |
| `--surface` | `#111214` | Main cards and panels |
| `--surface-raised` | `#17181C` | Popovers, menus, elevated sections |
| `--surface-muted` | `#202126` | Input backgrounds and quiet chart areas |
| `--border` | `#2B2C32` | Card outlines and dividers |
| `--text-primary` | `#F4F4F6` | Main headings and values |
| `--text-secondary` | `#B7B8C2` | Descriptions and labels |
| `--text-muted` | `#858692` | Axis labels and low-emphasis metadata |
| `--accent` | `#9B72F2` | Primary actions, active navigation, chart highlight |
| `--accent-strong` | `#7C4DFF` | Hover/pressed accent, used sparingly |
| `--success` | `#9BE34A` | Positive or healthy state with a text label |
| `--warning` | `#F6B94A` | Attention state with a text label |
| `--danger` | `#FF624F` | Error or critical state with a text label |
| `--chart-grid` | `#292A30` | Chart grid and separators |

These are proposed design tokens. Verify contrast and adjust as needed during implementation. Status colors must always be paired with text, icons, or shapes.

### Typography

- Use a modern, highly legible sans-serif such as Inter.
- Use a clear type scale rather than arbitrary font sizes.
- Dashboard page title: 24–30 px desktop.
- Card title: 14–16 px, medium weight.
- KPI value: 30–38 px desktop, responsive down on smaller screens.
- Body text: 14–16 px.
- Helper text and chart labels: 12–13 px, but never too faint to read.
- Use tabular numerals for metrics where available.
- Avoid long all-caps labels and avoid using thin font weights for key values.

### Shape and spacing

- Main dashboard padding: 24–30 px desktop; 16 px tablet; 12–16 px mobile.
- Card padding: 18–22 px desktop; 14–16 px mobile.
- Card radius: 16–20 px.
- Inputs and compact controls: 10–12 px radius.
- Use an 8 px base spacing scale.
- Keep card headers, metric baselines, and action positions aligned.
- Use consistent icon sizing and stroke weight.

---

## 3. Application Shell and Navigation

### Desktop shell

The dashboard should use a compact top navigation bar inspired by the reference:

- Left: EdgeErgo wordmark and a small, simple mark.
- Center/left: primary navigation.
- Right: global date-range control (where applicable), notification/status affordance if implemented, and user menu.
- Main content begins with a page title and a short contextual subtitle.
- Do not place every possible action in the top bar; use page-level actions for context-specific tasks.

### Primary navigation

1. **Overview** — current status and recent trends.
2. **Assessments** — assessment-event history and detailed observations.
3. **Devices** — enrolled workstations and sync/health state.
4. **Reports** — filtered summaries and CSV export.
5. **Settings** — account, preferences, privacy information, and authorized administrative settings.

Navigation visibility may depend on role, but backend authorization remains mandatory. An item being hidden in the UI is not a security control.

### Responsive navigation

- Desktop: horizontal top navigation.
- Tablet: compact navigation with shorter labels or a menu.
- Mobile: compact header and a menu/drawer; avoid squeezing five full navigation labels into a narrow bar.
- Maintain visible active state and keyboard focus.

---

## 4. Overview Dashboard

### Purpose

Answer these questions quickly:

- Is the system receiving assessment data?
- What does the selected time range show?
- Are there notable posture indicators or recurring patterns?
- Are devices online, offline, or waiting to synchronize?
- What action can the user take next?

### Page header

- Title: **Ergonomics Overview**
- Subtitle: a concise explanation of the selected date range and the scope of the data.
- Controls: date range, optional device filter (only for authorized roles), and a primary report/export action if relevant.
- Show last data update and whether the dashboard is connected to live service data.

### Suggested layout

First row — three or four KPI cards:

- **Assessments Recorded** — count of valid or total assessment events; label the exact definition.
- **Average Ergonomic Indicator** — only if a documented scoring method is implemented and the aggregation is scientifically appropriate.
- **Workstations Reporting** — reporting devices in the selected period, with denominator/context.
- **Sync Status** — pending or failed sync count, if available to the signed-in role.

Second row:

- **Assessment Trend** — line or area chart over time, with explicit units and date range.
- **Posture Indicator Breakdown** — a distribution by documented category or indicator, only when real data supports it.
- **Device Status** — compact summary of online, offline, and attention-needed devices for authorized users.

Third row:

- **Recent Assessments** — timestamp, permitted device label, validity state, score/category if valid, and a link to details.
- **Practical Guidance** — neutral, evidence-linked guidance based on real observations, or a clear empty state if no valid guidance is available.

The layout should remain flexible. Do not force all cards into the dashboard if the underlying data is not available or the user's role does not permit it.

### KPI card behavior

- Each card has a label, prominent value, definition/context, and optional comparison with a previous period.
- Do not show a percentage change unless the comparison period and calculation are defined.
- Use a dash or explicit “Not enough data” state instead of inventing a number.
- Make each card's meaning clear without requiring the user to interpret color.
- Clicking a card may navigate to a pre-filtered detail page only if that behavior is implemented consistently.

### Assessment trend chart

- Show dates/times along the horizontal axis and a clearly named measurement on the vertical axis.
- Include a tooltip with the date, value, sample count, and validity context when available.
- Use a restrained violet line or area.
- Include an accessible text summary below or alongside the chart.
- Never interpolate invalid observations in a way that implies measurements were collected.
- Display empty, loading, and error states.

### Insight or guidance panel

Use a visually distinct but restrained panel, optionally with a violet-tinted surface. Content must be based on actual data and explain its basis.

Good example: “Several valid observations in this period showed elevated shoulder positioning. Consider adjusting monitor and chair height, then reassess.”

Avoid: “You are a poor performer,” “This employee is unproductive,” or claims of emotion, stress, attention, or future injury.

If the system cannot support a reliable insight, show general setup guidance clearly labelled as general guidance—not as an AI-derived conclusion.

---

## 5. Assessments Page

### Purpose

Allow authorized users to inspect assessment records and understand why a score or recommendation was produced.

### Main components

- Page title and explanatory subtitle.
- Date range filter.
- Device filter where permitted.
- Validity/status filter.
- Scoring-method/version filter if more than one is supported.
- Search only over approved, non-sensitive fields.
- Paginated table or responsive list.
- Clear button to reset filters.
- Export action that respects the current filters and permissions.

### Table columns

- Timestamp.
- Device/workstation label (pseudonymous or configured label; avoid exposing unnecessary personal information).
- Assessment validity.
- Scoring method/version.
- Score/category, only when valid.
- Guidance summary, where available.
- Details action.

Do not display raw pose landmarks, camera frames, video, face crops, or inferred emotional states.

### Assessment detail view

- Timestamp and data freshness.
- Validity/confidence indicators with an explanation of their meaning.
- Scoring method/version.
- Relevant approved posture features.
- Score/category only if all required inputs were valid.
- Explanation of the factors contributing to the score, based on the documented methodology.
- Practical recommendations linked to observed indicators.
- Clear disclaimer that the result is a screening indicator, not a medical diagnosis.

If an observation is invalid, show why it was excluded and do not display a fabricated score.

---

## 6. Devices Page

### Purpose

Help administrators and authorized reviewers understand workstation enrollment, connectivity, and synchronization without exposing camera data.

### Device list/card fields

- Pseudonymous device ID or safe display label.
- Enrollment state.
- Active/revoked state.
- Last heartbeat or last-seen time, if implemented.
- Last successful synchronization.
- Pending queue count, if safely available.
- Agent version, if reported.
- Safe status label: Online, Offline, Sync Pending, Attention Needed, Revoked, or Unknown.

Define “online” precisely (for example, based on a recent heartbeat) and show when the status was last updated. Do not imply live camera access from an online device status.

### Device actions

For administrators only, as enforced by the backend:

- Create an enrollment token with expiry and single-use behavior.
- View token status without revealing a stored plaintext token after creation.
- Revoke a device credential.
- View safe device metadata and audit history.
- Rotate credentials through a defined secure workflow, if implemented.

Destructive actions require confirmation and a clear explanation of the effect. A revoked device must be unable to upload events.

---

## 7. Reports Page

### Purpose

Produce transparent, reproducible summaries from stored assessment records.

### Controls

- Date range.
- Authorized device or organization filter.
- Metric/category selection, if supported.
- Preview of the selected reporting scope.
- CSV export.
- Export progress and success/error feedback.

### Export requirements

- Apply the same access controls and filters as the on-screen data.
- Include useful column names, units, timestamps, scoring method/version, and validity status.
- Exclude secrets, raw camera media, raw landmarks, and data outside the user's authorization.
- Do not silently exclude invalid observations without explaining the rule.
- If a report contains no rows, explain that no matching records were found.

---

## 8. Authentication and Account Experience

### Sign-in

- Simple centered panel on a dark background.
- EdgeErgo brand and a concise purpose statement.
- Email/password or the configured Supabase Auth methods.
- Clear validation and authentication error messages.
- Password reset flow if enabled in Supabase.
- Loading state while authentication is in progress.
- Do not reveal whether an arbitrary email address belongs to an account beyond what the auth flow safely permits.

### Session behavior

- Restore a valid session on reload.
- Handle expired sessions and sign-out cleanly.
- Protected pages should not flash sensitive content before authentication is resolved.
- Backend requests must carry the user's access token.
- Role-based UI is for usability; the backend and database policies enforce permissions.

### User menu

- Account identity using only approved profile fields.
- Role label where appropriate.
- Privacy information.
- Sign out.

---

## 9. Settings and Privacy

Settings should be grouped into clear sections:

- **Account:** permitted profile preferences.
- **Display:** theme (if light mode is later supported), chart preferences, and density settings.
- **Notifications/reminders:** only settings that are actually implemented.
- **Privacy:** explain local camera processing, data synchronized, retention policy, and who can access summaries.
- **Administration:** organization/role/device controls visible only to authorized administrators.

Include a clear privacy statement:

“Camera frames are processed on this workstation. EdgeErgo does not upload raw video, face crops, or raw pose landmarks. Only the configured assessment summaries and necessary operational metadata are synchronized.”

This statement must be verified against implementation and network traffic before release.

---

## 10. Windows Desktop Agent UI

The desktop agent is not the same interface as the web dashboard. Its UI should be compact, unobtrusive, and focused on the workstation user.

### Overlay appearance

- Small dark translucent or solid charcoal panel.
- High-contrast text and a restrained violet accent.
- Minimal information: current state, latest valid indicator, one short recommendation, last update, and sync status.
- Clear Pause/Resume and Settings controls.
- No charts or dense tables in the overlay.
- Do not steal keyboard focus or obstruct normal work.

### States

- **Ready:** camera has not started or the agent is ready to begin.
- **Active:** local analysis is running.
- **Paused:** the user has paused analysis.
- **Camera unavailable:** permission denied or camera not found.
- **Low confidence:** insufficient reliable landmarks; no score displayed.
- **Offline:** local analysis continues, sync is queued.
- **Syncing:** approved events are being uploaded.
- **Authentication error:** device credential rejected; stop upload and explain the safe next step.
- **Error:** a recoverable or fatal error with a clear message.

### Feedback language

Use brief, neutral, actionable prompts. Examples:

- “Try relaxing your shoulders and keeping them level.”
- “Your screen may be too low; consider checking monitor height.”
- “Take a short movement break when convenient.”
- “Not enough reliable posture information to calculate a score.”

These are examples only. Final recommendations must be tied to validated indicators and reviewed scoring logic.

### Privacy indicator

The agent must make it obvious when camera analysis is active. Include a persistent state indicator and a simple explanation of what stays local and what synchronizes. Do not store images or video by default.

---

## 11. Responsive Behavior

### Desktop: 1200 px and above

- Use a 12-column or equivalent responsive grid.
- KPI cards align in one row where space allows.
- Charts and tables receive sufficient width.
- Keep page content within a comfortable maximum width; avoid stretching charts edge-to-edge on ultrawide displays.

### Tablet: 768–1199 px

- Reduce grid columns.
- KPI cards may use two columns.
- Stack complex chart panels when labels or tooltips would become cramped.
- Convert the navigation to a compact layout.

### Mobile: below 768 px

- Single-column content flow.
- KPI cards use a two-column grid only if values remain readable; otherwise stack them.
- Charts must remain legible and support horizontal overflow only where necessary.
- Tables become responsive cards or a carefully designed scrollable region.
- Filters move into a filter panel or drawer.
- Buttons have comfortable touch targets (aim for at least 44 × 44 CSS px).
- Avoid tiny axis labels and overly dense data visualizations.

The dashboard is for reviewing assessment summaries; camera capture and posture inference remain in the Windows agent.

---

## 12. Interaction States and Feedback

Every data-driven page must include:

- **Loading:** skeletons or a clear loading indicator without fabricated values.
- **Empty:** explain why no records are available and offer a relevant next step.
- **Error:** concise explanation and retry where safe.
- **Success:** confirm completed actions such as export or token creation.
- **Permission denied:** explain that the account lacks access without leaking protected details.
- **Stale data:** show the last successful update when freshness matters.
- **Partial data:** indicate missing or invalid observations rather than presenting totals without context.

Forms must validate inputs and show errors close to the relevant field. Destructive actions require confirmation. Disabled controls should explain why they are unavailable when the reason is not obvious.

---

## 13. Accessibility

- Use semantic headings, navigation, tables, buttons, and form labels.
- All controls must be keyboard-operable with visible focus.
- Maintain sufficient text and control contrast against dark surfaces.
- Never communicate state using color alone; pair colors with labels/icons.
- Provide accessible names for icon-only buttons.
- Provide text summaries for charts and non-visual alternatives to important chart information.
- Respect reduced-motion preferences.
- Ensure validation errors are announced and associated with their inputs.
- Do not use very small text for important safety, privacy, or data-validity explanations.

---

## 14. Motion and Micro-interactions

Use motion sparingly:

- Short transitions for hover/focus and panel expansion.
- Subtle chart transitions only when they do not distract or obscure data changes.
- Clear progress feedback for sign-in, exports, and device enrollment.
- No looping decorative animation in the main dashboard.
- Respect reduced-motion settings.
- Avoid effects that make a metric appear to change when no new data has arrived.

---

## 15. Data Visualization Rules

- Every chart has a title, time range, units, and definition.
- State whether the data is a count, percentage, average, distribution, or score.
- Show sample counts when they affect interpretation.
- Define comparison periods before displaying changes.
- Do not combine different scoring methods into one average unless the methodology justifies it.
- Invalid observations must not be silently treated as zero.
- Missing data must not be drawn as a real measurement.
- Use violet for the primary series and neutral tones for supporting series.
- Use status colors sparingly and consistently.
- Tooltips must be usable with keyboard and pointer interaction.
- If no valid data exists, show an explanatory empty state rather than a blank chart.

---

## 16. Content and Terminology

Prefer:

- “Ergonomic indicator”
- “Assessment”
- “Observation”
- “Valid / Insufficient data”
- “Workstation”
- “Practical recommendation”
- “Last synchronized”
- “Device status”

Avoid:

- “Employee performance score”
- “Productivity ranking”
- “Emotion detection”
- “Stress score”
- “Injury prediction”
- Any language implying diagnosis or certainty beyond the validated method.

Use consistent date/time formatting and show the timezone when it matters. Use plain language for error messages and technical detail in expandable diagnostics where appropriate.

---

## 17. Design Acceptance Checklist

- [ ] The dashboard follows the dark, rounded-card, violet-accent visual direction.
- [ ] Typography, spacing, radii, borders, and colors use consistent tokens.
- [ ] Overview metrics are sourced from real data and have definitions.
- [ ] Loading, empty, error, stale, partial-data, and access-denied states exist.
- [ ] The dashboard never presents sample values as real production values.
- [ ] Invalid observations do not produce fabricated scores.
- [ ] Assessment details explain score validity and methodology.
- [ ] Device status does not imply remote camera viewing.
- [ ] The dashboard contains no raw images, video, face crops, or raw pose landmarks.
- [ ] Authentication and role-specific UI are integrated with backend authorization.
- [ ] Mobile and tablet layouts are usable without clipped content.
- [ ] Keyboard navigation, focus, contrast, labels, and chart summaries are tested.
- [ ] The Windows overlay is compact, non-intrusive, and explicit about camera state.
- [ ] Privacy statements match the implemented data flow.

## 18. Implementation Guidance for Antigravity

Use this document alongside `PRD.md` and `TECH_STACK.md`.

1. Inspect the existing project and keep the chosen stack.
2. Establish design tokens and shared layout components before building individual pages.
3. Implement the application shell, navigation, responsive grid, typography, and core components first.
4. Build the overview using real API contracts; use clearly labelled fixtures only in development and never as production data.
5. Implement loading, empty, error, and permission states with each feature, not as a final polish task.
6. Keep chart and card components reusable and accessible.
7. Implement the Windows overlay separately from the web dashboard.
8. Validate the design at desktop, tablet, and mobile sizes.
9. Do not add metrics, AI insights, or controls unless the backend and PRD support them.
10. Report actual files changed, tests run, and remaining design gaps after each phase.
