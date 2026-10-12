# House style — the voice specification

**What this file is.** The register of everything the plugin writes to be spoken or sent: run-sheets, scoping run-sheets, recaps and client-facing replies. `demo-script` and `call-intake` read it and never restate it (A§3.12). It is a shipped shared file: no skill or script edits it, the knowledge overlay does not touch it, and it changes only in a release, after the regeneration step in `MAINTAINING.md` (A§10.3). Section numbers below are the method's (§n) and the architecture's (A§n); the shipped homes of the rules linked here are `shared/sales-method.md` (method §4.10 and §7) and `shared/safety.md` (A§9.11 and 9.12).

**Two things it is not.** It is not a script: every shape is adapted to the meeting, never read out (method §0). And it is not a portrait of a person: it describes a register per speaker and per seat (section 2) and names nobody.

## 1. Register targets

The targets are stated as properties a generator can check on its own output, not as rates. The measurements behind them were taken per speaker on a corpus that does not ship, and a rate quoted here without its sample would be read back as a rule.

| Target | What it looks like | What it is not |
|---|---|---|
| Assertive rather than hedged | A claim is stated plainly, or it is not made | Softeners stacked in front of a claim |
| Mechanism-first | The construct is named, defined in one plain sentence, then restated in their nouns and verbs | The feature name, then a list of benefits |
| Hedging explicit and structural | "I'd want to check that before I promise it — [name] confirms by [day]": an owner, a date, no figure in the same turn | Atmospheric hedging: adverbs, "probably", a range said aloud |
| Prepared over capable | The opening proves the pre-read; capability is shown on screen | An opening built on what we can do |
| Every question routed | To a named person, with the reason they own it | A question to the room |
| Their vocabulary | Each construct anchored to something they already use; each term of art dissolved on first use | Platform jargon carried through the meeting |
| Short, plain sentences | One idea per sentence; the plain word over the technical one | Compound sentences with stacked qualifiers |
| Correctable | Each proposal ends by inviting the missing case | "Does that sound good?" |

Written output — a recap or a reply — keeps the same register: short, plain, in the client's words, no method vocabulary, and no figure a group-facing text may not carry (method §6.2, §4.10).

## 2. Profiles are per speaker and per seat

A profile is built from one speaker's own turns in one seat. Nothing is pooled across our side, because a pooled profile puts a colleague's habits in the user's mouth: measured on the calibration corpus, one colleague's hedging tic ran at many times the user's rate, and a pooled bank would have carried it into every generated sheet (A§3.12).

Seat is the first dimension of the call-type header (`call-intake/references/call-types.md`, A§8.3 step 5): who owns the room and the question order — partner-led, co-sell, vendor-led, client-led. The same speaker frames, routes and handles money differently across seats, so the sample is kept per seat as well.

**Eligibility.** `call-intake` marks an own-side turn eligible for the bank only when its side-internal attribution is unambiguous, and excludes any turn adjacent to a same-side turn whose content could belong to either speaker. The corpus holds a clean specimen of why: one recommendation that decided an engagement's tooling is labelled to the person who asked the question it answers, and either reading is coherent. The marks exist for the regeneration step (section 7) and for nothing else in v1.

**Sample and provisional marks.** The bank rests on a large sample in one seat and a much smaller sample in another. The shapes drawn from the smaller sample — the framing, mechanism and commercial families of section 5 — are marked *provisional*. The observation that confirms them: a second call in that seat, with the user's own-side turns marked eligible, in which the shape recurs in the user's own turns. Until then they ship as hypotheses; regeneration is how one is promoted, and release check 10 confirms none was promoted without that observation.

## 3. DO

Each item carries its reason, because a rule without one is dropped under pressure in the room.

1. Open with who you are, who is with you and why, and what you already know from the pre-read. Proof of preparation beats a capability list.
2. Define the platform once, in one plain sentence, whenever anyone present has not seen it, and dissolve each term of art the moment it is used. Jargon left standing is a question nobody asks.
3. Anchor every new construct to whatever they already use. A thing with a known neighbour is understood; a thing without one is memorised.
4. Prefer building live on screen to describing. A built thing gets corrected; a described one gets agreed to politely.
5. Stop before a dependency and ask, rather than assume a fact about the client. Where an input lives today and who puts it there decides whether the next screen is true.
6. Route every question to a named person with the reason they own it. A question to the room is answered by whoever is most comfortable, not by whoever knows.
7. Ask the same architecture question twice: once of whoever knows what is possible, once of whoever knows what is needed. The two answers differ, and the difference is the design.
8. Mark the load-bearing primitive and confirm it before composing on it. Everything after a wrong primitive is wasted.
9. Convert a client statement into a named mechanism: define the name at once in plain words, then restate it in their world. A name they can repeat is a thing they can approve.
10. Close each proposed mechanism with a correctability question, which invites the missing case rather than an opinion. "What case does that miss?" gets a case; "does that sound good?" gets a review.
11. Admit unfamiliarity and make the admission the reason for the question. It buys the question and costs nothing.
12. Narrate fumbles and say why a screen is messy. Silence over a mess reads as concealment.
13. Retract explicitly and attribute the correction. A quiet correction is remembered as the original claim.
14. Deflate scope when it is genuinely small. Trusted expert, not order taker (method §1).
15. Anchor money against a spend they already make, and check entitlement before quoting. A figure with no anchor is compared with zero (method §4.10).
16. Ask for their example artefact before offering ours. Theirs shows what the build has to fit.
17. Let them talk first, and pause after every question (method §4.1, §4.2). In discovery they carry most of the talking.

## 4. DON'T

The DON'Ts are the claims and confidentiality rules stated in the second person, and they are links. Each row names the rule in a clause and points at the one place it lives with its reasons; nothing here restates a rule, so a rule changes in one file. Item numbers are method §7's.

| You do not... | Where the rule lives |
|---|---|
| State a figure you cannot source; you refuse, never range, and a commitment to check carries no figure in the same turn | method §7.1; A§9.12 |
| Say "it can" for anything not shown or buildable; unverified goes to the if-asked list with its sentence | method §7.1, §4.1 |
| Answer a plan-gated question without its gate, or state a plan, quota or entitlement figure not read live at prep with its date | method §4.10, §7.1; A§9.12 |
| Estimate effort, duration or completion for unbuilt or unread work in front of whoever will price it | method §7.1 |
| Claim a capability, limit or flexibility of a system nobody on our side has read | method §7.1 |
| Say "we can change it later" unqualified | method §7.1 |
| Cite client counts, usage statistics, sector experience or demand for our own services — in the self-introduction above all | method §0; §7 item 16 |
| Promise maintenance-free anything, or assert a vendor's data-handling position as ours | method §7 items 15 and 17 |
| Say anything on the never-say list, which `demo-script` reads at generation | `shared/monday-gotchas.md`, never-say block (A§10.2) |
| State a price, rate, entitlement or account-status figure after the approver has left, in a group recap, or through a non-approver | method §4.10; A§9.12 audience routing |
| Ask a leading price question, or reason from one vendor's pricing to another's | method §4.10 |
| Repeat a colleague's earlier figure or promise unverified, or restate a third party's claim as ours | method §7.1; A§9.12 |
| Open, or steer anyone to, our own live operational account or any of its data | A§9.11; `shared/sandbox-accounts.txt` ids marked `never-demo` |
| Mention a client's personal login as an access option — not as a hypothetical, not while naming the risk; the one access-request shape is a named seat | A§9.11; method §7 item 19 |
| Describe a permission as verified when it could only be recorded configured: board level is provable through the board's `permissions` field, everything below it is `not-checkable` | method §7 item 20; `shared/read-back.md` permissions row [doc, P-18] |
| Let internal vocabulary, grades, objections, stakeholder reads or another client's name reach anything client-facing or a shared screen | method §7 items 1 to 14 |
| Name more than one tool category in a sentence outside a call folder | method §7, the authoring rule |

Two rules of this file's own:

- **Never run past a couple of minutes without a routed question.** A monologue is not a demo (method §1). The generator's clock is method §4.3's: about ninety seconds since the last client word, counted across both presenters, and the next scripted line is a routed question.
- **Never let a client have to apologise for interrupting.** The opening frame invites interruption; when one comes, the next line takes it and their thread is finished before ours resumes — the redirect rule of method §4.5.

## 5. Sentence shapes

Placeholders sit in [brackets]. No shape carries a proper noun, a figure, a product, brand or platform name, or a client's words, and the leak lint runs over this file at release like any other shared file. A family marked *provisional* is a smaller-sample family (section 2), confirmed by a second eligible call in that seat. Every phrasing is adapted to the meeting; none is read out.

**Framing** *(provisional)*
- Who and why: "I'm [role]; [colleague] is here because [reason]."
- Pre-read: "From what you sent over I know [fact] and [fact]. Tell me where that's already wrong."
- The platform, once: "[The platform] is [one plain sentence]. A [term] is just [plain word]."
- Anchor: "This is your [their thing], with [difference]."
- Structure translation (method §4.2): "Today it's one [container] per [X] with each [Y] inside; here the [Y] becomes [this] and the [container] becomes [that]."
- Build rather than tell: "Rather than describe it, I'll build it while you watch — stop me at the first wrong step."

**Routing**
- Named, with the reason: "[Name], this one is yours because you run [thing]: [question]?"
- Twice: "[Name], is that possible today?" then "[Name], is that what you actually need?"
- Before a dependency: "Before I go further — where does [input] live today, and who puts it there?"
- The named check-in (method §4.3): "[Name], how close is this to what you had in mind?"
- The room-wide open check-in, at a phase boundary only: "On [topic] — is there anyone whose week this touches that we haven't heard from?"
- Taking an interruption: "Go on — that's what this is for."

**Mechanism** *(provisional)*
- Primitive first: "Everything hangs off [primitive]; if that's wrong, nothing after it holds — is it right?"
- Convert: "What you just described — [their words] — I'd call [mechanism]: [one plain sentence]. In your world that means [restated in their nouns and verbs]."
- Correctability: "What case does that miss?"
- Two shapes: "Both work: [A] or [B]. [A] costs you [this]; [B] costs you [that]. You choose."
- Deflate: "That part is small; I'd do it in the session rather than write it up."
- Artefact first: "Send me one of yours first."

**Not knowing, not being able, self-correcting**
- Unfamiliarity as the reason: "I haven't seen your [system]; that's why I'm asking what a [record] looks like."
- Check, without a figure: "I'd want to check that before I promise it — [name] confirms by [day]."
- The positive continuation: "The honest answer is to build the smallest version, run it once, measure, and multiply by your own volume."
- Unread work: "I've seen [this]; I'd need to look at [that] before I put a number on it — can you send [artefact]?"
- Plan gate, plan unknown: "That depends on your tier; I'll confirm which side of the line you're on by [day]."
- A permission (P-18): "The board-level setting I can prove after the build; the restriction below it I configure, and we check it together by eye."
- Fumble: "That screen is messy because [reason]; give me a moment."
- Retract: "Earlier I said [X]; that was wrong — [Y] is right, and [name] caught it."
- A third party's claim: "That's [their] claim, not mine; their published documentation is where your review should look."

**Commercial** *(provisional)*
- Metered disclosure, early and unprompted wherever a component is metered (method §4.10; credits for elements that consume them, A17): "[Component] is consumption-priced: you pay by [unit]. I'll read the rate off your account before I quote it."
- Anchor: "Set against what you already spend on [existing spend], here is what this replaces."
- Entitlement first: "Before I quote, I'll check what your tier already includes."
- Refusal, not a range: "I don't have a sourced number for that, so I won't guess one; [name] confirms it by [day]."
- Approver absent: "That's [approver]'s question; I'll put it to them by [day] rather than answer it here."

**Close** (method §4.6)
- Commitment, not summary: "From what you've seen, does this deal with the problem you described?" then "Where would you like to go from here?"
- Per-pain, from the confirmation ledger: "[Name], you said [their tie] — is that right?"
- Gap and backlog: "You asked for [ask]; that goes to [the next version / the backlog], and [ask] we didn't show."
- Hesitation: "What could get in the way?"
- Mechanism: "[Owner] sends the invite while we're on the call; failing that, [mechanism] by [day]."

**Sent, not spoken** (recap and reply, method §6.2)
- "What we heard: [two to four bullets, their words]. What we agreed: [items]. Next step: [date, time, who — or the mechanism and its owner]. What we need from you: [commitments, dated]. What you'll get from me: [commitments, dated; every deferred answer now owned]."
- A reply answers the question asked in its first sentence, gives the reason, then names the one thing we need from them.

## 6. The opening frame and the credential slot [L18]

The run-sheet's opening frame is the who-and-why line, then three sentences (method §4.2): what each piece links back to ("Each piece I show links to something you told me. Interrupt whenever you like."), the plan boundary (what their tier includes and what is shown from another), and the seeded-data boundary (what on screen is theirs and what is illustration). Then a priorities question, not a recap: "Has anything shifted since we last spoke?"

Between the who-and-why line and the three sentences sits **one slot for one verifiable credential** — a certification, a listed status, a named reference the client may contact — the substitute method §0 allows for the banned client-count claim in a room where our side is a stranger. The generator renders the slot and leaves it empty, as this literal line:

`Credential: empty [L18]`

That line is what `demo_check.py gate` looks for (H51). The generator never fills it, and no sentence that would use it is generated while it is empty. What stands there is the user's to decide, before the first partner-led run-sheet is generated, because in a partner-led seat no third party is present to vouch (A§13, lessons decision 18). A credential is a claim about us, so the no-claims rule of method §0 applies: the user supplies it and approves it, and the generator never infers one from research.

## 7. Maintenance

- This file changes only in a release. The regeneration step in `MAINTAINING.md` runs on the Mac (A§5.1, the surface that holds credentials), over records the user chooses; it reads only own-side turns the intake report marked eligible, produces shapes with placeholders and no client content, passes them through `leak_lint.py --terms`, and the user reviews them before the file changes (A§3.12).
- A provisional family is promoted only with its confirming observation recorded in section 2; release check 10 confirms the mark is still here otherwise.
- The file obeys its own rules: no personal name, no proper noun in a shape, tool references as category words with at most one category per sentence.
