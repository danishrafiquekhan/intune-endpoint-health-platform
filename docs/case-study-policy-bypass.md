**Case study: policy bypass via personal browser profile**

Genericized from a real investigation — fake app names, fake policy names,
no real device or user identifiers.

**What happened**
A user reported that a Progressive Web App we push through Intune-managed
Chrome policy — I'll call it "AcmeApp" here — wouldn't install, or would
install and then immediately misbehave (missing the taskbar/dock pinning
behavior we expect, prompting for permissions it shouldn't need to prompt
for). The device showed compliant in Intune. The Chrome management policy
that should have controlled this (call it `PWAInstallForced` — a policy
pushing `WebAppInstallForceList`-style enforcement) showed as applied when
checked through `chrome://policy` on some sessions, and simply absent on
others, on the same physical machine, for the same signed-in Windows user.
That inconsistency — same device, same policy, different result depending
on something we hadn't identified yet — was the actual clue, even though it
took a while to register as one.

**Why it was tricky**
The first assumption was a device compliance or configuration profile
problem: maybe the Chrome ADMX policy wasn't targeting the right Azure AD
group, maybe there was a conflicting GPO-equivalent CSP, maybe the device
had fallen out of the deployment ring that had the policy. All reasonable
things to check first, all of which came back clean — the Intune
configuration profile was correctly assigned, `chrome://policy` did show
`PWAInstallForced` as a known policy source on the machine, and other
managed Chrome policies (extension allowlist, safe browsing enforcement)
were visibly working on that same device. That last part was the detail
that should have redirected the investigation sooner: if the device-level
policy delivery were actually broken, *all* Chrome-managed policy would be
missing, not just this one behavior. Instead only the PWA-related enforcement
was inconsistent, which pointed at something scoped narrower than the
device — but it took ruling out compliance state, profile targeting, and
deployment ring assignment first before that narrowing made sense.

**Root cause found**
The inconsistency tracked to which Chrome **profile** the user had open,
not the device. Chrome supports multiple profiles per Windows user account,
and only a profile that Chrome recognizes as the managed/work profile
(tied to the org's identity and picking up cloud policy for that profile)
inherits Intune-enforced Chrome policy the way we expected. The user had a
personal Chrome profile — signed into a personal Google account, set up
before the device was enrolled, still sitting in the profile picker — and
was doing day-to-day browsing in it out of habit. Policies like
`PWAInstallForced` that are scoped to the managed profile simply don't
apply inside a personal profile; from Chrome's point of view, the personal
profile isn't the org's context, so there's nothing forcing it to obey
org-scoped policy. The device was compliant, the configuration profile was
correctly targeted, and the policy genuinely was pushed to the device —
none of that mattered because the browser session in front of the user
wasn't the profile that policy was scoped to.

**Fix applied**
Two parts:
1. **Immediate fix for the reported case**: had the user switch to (or
   create) a Chrome profile tied to their org identity, confirmed
   `PWAInstallForced` showed as applied in `chrome://policy` under that
   profile specifically, and the PWA install/behavior worked as expected.
2. **Structural fix**: enabled `BrowserSignin` / managed-profile enforcement
   policy (the Chrome ADMX setting that requires the browser to be signed
   into a managed profile to be usable, or that redirects browsing into the
   managed profile) so a personal profile can't silently sit alongside the
   managed one and absorb everyday use. This doesn't retroactively fix every
   personal profile already in use across the fleet, but it stops new
   instances of the same failure mode and makes "which profile is this
   policy actually scoped to" a question that gets forced early instead of
   discovered during a support ticket.

**Detection concept — and why it stays conceptual**
The natural next question is whether this is something we could detect
automatically instead of relying on someone filing a ticket: flag a device
where a policy-managed application is running under an unmanaged/personal
browser profile context.

Being honest about where this stands: **Intune doesn't natively expose
Chrome profile-level telemetry.** Device compliance and configuration
profile state are visible in Intune; which Chrome profile a given browser
window or PWA session is running under is not something Intune, as far as
I've found, surfaces as a queryable signal. So there's no real KQL/Sigma
rule to write against Intune/Defender data today that says "policy X is
scoped to profile Y and this session is profile Z" — I don't want to fake
one that looks like it works and doesn't.

What the detection would conceptually need, if the telemetry existed:
- A signal for **which Chrome profile** is active for a given browsing
  session or app launch — profile identity (managed vs personal, and which
  org/account it's tied to), not just "Chrome is running."
- A signal for **which policies are scoped to which profile** — i.e. "is
  `PWAInstallForced` currently applied in the profile that's actually
  active," which is closer to what `chrome://policy` shows locally than
  anything centrally aggregated today.
- Some way to correlate the two per-session, so the logic is roughly:

  ```
  for each active Chrome session on a managed device:
      if session.profile_type != "managed"
         and session.org_scoped_policies_expected_here == true:
          flag: "policy-managed app/session running outside managed profile"
  ```

  That's pseudocode describing the shape of the check, not a rule against
  any real schema — I don't have a data source that populates
  `session.profile_type` or `org_scoped_policies_expected_here` today.
- The closest thing that's realistically actionable without new telemetry:
  a compliance check or login script that inventories Chrome profiles
  present on a managed device and flags (or blocks) the presence of a
  signed-in personal Google profile at all, regardless of what's running in
  it — cruder than detecting the policy bypass directly, but buildable with
  what's actually available (enumerating Chrome's `Local State` /
  `Profile` directories on disk), where the profile-scoped policy telemetry
  isn't.

So: this stays a well-written case study plus a sketch of what proper
detection would require, not a working rule. If Chrome/Intune telemetry
around profile identity becomes available (or if there's a Defender/Chrome
Enterprise Core signal I've missed), this is the first thing I'd go back
and build for real.
