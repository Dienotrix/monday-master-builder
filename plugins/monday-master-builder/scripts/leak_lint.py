#!/usr/bin/env python3
"""The leak lint (ARCHITECTURE 9.6; WP4 decisions X01 to X47, Y01 to Y09 and Z01 to Z19).

leak_lint.py keeps internal details, and other clients' details, out of anything the plugin writes into monday.
It reads a draft, a .docx or a payload, checks it against the shipped list, the user's local list and settings,
the client record's own figures, quotes, internal text and exclusions, and the cross-client wall, and reports. It
never edits a file, it writes nothing but the index (which `index` alone writes) and it never calls monday. Every
command prints one JSON object, {"ok", "command", "verdict", ...}, and exits 0 (clean), 1 (blocked), 2 (warnings
or cautions only) or 3 (could not run, which every caller treats as a stop). Standard library only, Python 3.9
and later, the same on Windows and macOS.

Six commands: `scan` (drafts, summaries, client-safe blocks), `payload` (one tool input), `blueprint` (the planned
text of one strand), `wall` (the wall alone on one text), `terms` (a folder, for the release check) and `index`
(this record's entry in <home>/clients-index.json).
"""
import sys
sys.dont_write_bytecode = True  # no cache beside the scripts (G49), set before mmb_common is imported


def python_too_old(version=None):
    """The envelope for an interpreter older than 3.9, or None (L206)."""
    found = tuple(version or sys.version_info[:2])[:2]
    if found >= (3, 9):
        return None
    return ('{"ok": false, "command": null, "verdict": "could-not-run", "error": {"file": "leak_lint.py", '
            '"field": "python", "problem": "Python %d.%d", "expected": "Python 3.9 or later"}}\n' % found)


if python_too_old():
    sys.stdout.write(python_too_old())
    sys.exit(3)

import argparse, bisect, hashlib, html, io, json, os, re, stat, unicodedata, zipfile  # noqa: E401,E402
import xml.etree.ElementTree as ET  # noqa: E402
from datetime import date, datetime, timezone  # noqa: E402
from fractions import Fraction  # noqa: E402
from pathlib import Path, PurePosixPath  # noqa: E402
import mmb_common as mc  # noqa: E402

# pinned: leak
MARKERS = ("[Q]", "[Q?]", "[Q/side]", "[Q/recon]", "[Q/doc]", "[X]", "[E]", "[I]", "[A]")
KINDS = ("workspace", "folder", "board", "group", "column", "view", "form", "subitems", "doc", "dashboard", "widget",
         "automation", "portfolio", "project", "workflow", "agent", "ai_column", "vibe_app", "sequence", "webhook",
         "item_batch", "publication", "activation", "generic")
FAMILIES = ("name", "description", "label", "seed", "markdown", "request_text", "role", "role_description", "goal",
            "plan", "user_prompt", "knowledge_name", "prompt", "app_name", "step_text", "recipient", "url")
KIND_FAMILIES = ((("agent",), ("name", "role", "role_description", "goal", "plan", "user_prompt", "knowledge_name")),
                 (("vibe_app",), ("prompt", "app_name")),
                 (("ai_column",), ("name", "prompt")),
                 (("workflow",), ("name", "description", "step_text")),
                 (("sequence",), ("name", "step_text", "recipient")),
                 (("webhook",), ("url",)),
                 (("automation",), ("name", "request_text")),
                 (("item_batch",), ("name", "seed")),
                 (("doc",), ("name", "markdown")),
                 (("workspace", "folder", "board", "group", "column", "view", "form", "subitems", "dashboard", "widget",
                   "portfolio", "project", "publication", "activation"), ("name", "description", "label")),
                 (("generic",), FAMILIES))
BLOCK_MARKS = ("<!-- client-safe:start -->", "<!-- client-safe:end -->", "<!-- glossary:start -->",
               "<!-- glossary:end -->")
HEADINGS = ("## Conflicts", "## Exclusions", "## Allowlist")
ROW_KEYS = ("kind", "added", "by", "source", "ok", "date", "class")
EXCLUSION_KINDS = ("name", "term", "figure")
INDEX_FIELDS = ("clients-index/1", "schema", "hash", "normalisation", "entries", "updated", "names", "phonetic",
                "terms", "figures")
INDEX_FORMS = ("sha256-128", "wall/1")
SEVERITIES = ("block", "warn", "caution")
VERDICTS = ("clean", "warnings", "blocked", "could-not-run")
MODES = ("full", "summary", "client-safe-block", "blueprint")
RULES = ("term", "phonetic", "seller-account", "figure", "split-figure", "copied-run", "quote", "exclusion", "wall",
         "credential", "internal-note", "paraphrase", "number", "record-number", "allowlist")
WALL_CLASSES = ("name", "term", "figure", "slug")
CLEARABLE = ("method", "internal-vocabulary", "sales-framing", "assessment", "emotional", "health-identity",
             "departure", "colleague-remark", "personal-life")
LOCAL_CLASS = "local"
# end pinned

# pinned: common-words
# About a thousand ordinary English words and about sixty monday and work words, lower case, with the
# apostrophes of contractions removed as the tokeniser removes them (X19). A six-word stretch counts toward
# the copied-run rule only when RUN_MIN_DISTINCT of its words are outside this list; a number always is.
COMMON_WORDS = frozenset("""
a able about above across act action actual actually add added adding after afternoon afterwards again against
age ago agree agreed ahead air all allow allowed almost alone along already alright also although always am among
amount an and another answer answered any anybody anyone anything anyway anywhere apart appear apply applied april
are area areas arent arm around arrive arrived as ask asked asking at august available away back bad bag ball bank
bar base basic basis be became because become becomes been before began begin beginning behind being believe below
beside best better between beyond big bit black blue body book books both bottom bought box boy break bright bring
brings brother brought brown build builds built busy but buy by call called calling calls came can cannot cant car
card care careful carry carried case cases catch caught cause certain certainly chance change changed changes check
checked checking child children choice choose chose city class clear clearly close closed club cold colour color
come comes coming common company complete completely condition consider considered continue continued corner
correct could couldnt country couple course court cover covered create created cup current currently cut cuts
daily dark data date dates day days dead deal dear december decide decided decision deep degree describe design
detail details develop did didnt different difficult direct direction do does doesnt doing done dont door doors
down draw drew drink drive drop dropped due during each earlier early earth easily easy eat effect effort eight
either else elsewhere empty end ended ending ends energy enough entire equal even evening event events ever every
everybody everyone everything everywhere exact exactly example except expect expected experience explain explained
extra eye eyes face fact fair fall family far fast father february feel feeling feels fell felt few field fifth
figure fill filled final finally find finds fine finish finished first five fix fixed floor follow followed
following food foot for force form former forward found four fourth free friday friend friends from front full
fun further future game garden gave general get gets getting girl give given gives giving glad glass go goal goes
going gone good got gotten great green ground group grow growth guess had hadnt half hall hand hands happen
happened happens happy hard has hasnt have havent having he head health hear heard heart heavy held hello help
helped helps hence her here hers herself hes high him himself his history hold holds home hope hoped hour hours
house how however huge hundred i id idea ideas if ill im important in include included includes including indeed
information inside instead interest interesting into is isnt issue issues it item items itll its itself ive january
job jobs july june just keep keeps kept key kind knew know known knows land language large last late later law learn
learned least leave leaves led left less let lets level life light like liked likely likes line lines list listen
little live lived local long look looked looking looks lose losing lost lot lots love low made main major make makes
making man many march matter may maybe me mean means meant meanwhile meet meeting meetings meets member men message
met method middle might million mind mine minute minutes miss moment monday money month monthly months more moreover
morning most mostly mother move moved moves much must my myself name names nature near nearly necessary need needed
needs neither never new news next nice night nine no nobody none nor normal not note notes nothing november now
nowhere number numbers october of off offer offered office often oh ok okay old on once one only onto open opened
opens or order orders other others otherwise our ours ourselves out outside over own page pages paper part particular
parts party pass passed past pay people per perfect perhaps period person phone pick picked picture piece place
places plan planned plans play played please point points policy position possible power practice prefer prepare
prepared present pretty price probably problem problems process product program project proper provide provided
public pull push put puts question questions quick quickly quiet quite rather reach read reading reads ready real
really reason receive received recent recently record records red remember remove removed reply report reported
rest result results return right road role room round rule rules run running runs safe said same saturday save
saved saw say saying says school second see seeing seem seemed seems seen sell send sends sense sent september
serious set sets seven several shall shape she shes short should shouldnt show showed shown shows side sign similar
simple since single sit six size skill slow small so soft some somebody someone something sometime sometimes
somewhere soon sort space speak special spend spent staff stage stand start started starts state stay stayed step
steps still stop stopped story street strong student study subject such suggest suggested sunday support sure
sweet system table take taken takes taking talk talked talking tall task team tell telling tells ten term terms test
than thank thanks that thats the their theirs them themselves then there thereafter therefore theres these they
theyd theyll theyre theyve thing things think thinking thinks third this those though thought thousand three
through throughout thursday thus time times to today together told tomorrow tonight too took top total toward
towards town tree tried tries trip true truth try trying tuesday turn turned two type under understand unit unless
until up update upon us use used uses using usual usually value various very via view voice wait waiting walk wall
want wanted wants war warm was wasnt watch water way ways we weak wed wednesday week weekend weekly weeks well went
were werent weve what whatever whats when whenever where wherever whether which while white who whoever whole whom
whose why wide wife will window with within without wont word words work worked working works world would wouldnt
write writes writing written wrong wrote year yearly years yellow yes yesterday yet you youd youll young your youre
yours yourself yourselves youve
board boards subitem subitems status statuses groups column columns owner owners timeline timelines dashboard
dashboards views form forms automation automations workflow workflows updates task tasks project projects team
teams client clients customer customers reports request requests file files doc docs document documents priority
priorities stages deadline deadlines workspace workspaces folder folders label labels tag tags assign assigned
assignee approval approvals approve approved review reviews comment comments link links template templates track
tracking schedule schedules email emails call contact contacts sheet sheets quote quotes service crm dev vibe
management manager admin user users account accounts
""".split())
RUN_MIN_DISTINCT = 2
# end pinned

# pinned: stop-words
# The stop list of X26 beside the common words: monday's product words, titles, role acronyms and common acronyms.
# The wall's name harvest (part 2) drops them; the shipped plugin, assistant, method and marker rows join it at run
# time.
PRODUCT_WORDS = frozenset(("monday", "work", "management", "crm", "service", "dev", "vibe"))
STOP_WORDS = frozenset(("mr", "mrs", "ms", "mx", "dr", "prof", "sir", "ceo", "cfo", "coo", "cto", "vp", "hr", "it",
                        "pm", "pms", "qa", "crm", "erp", "sop", "api", "eta", "pdf", "kpi", "roi", "sla", "faq", "uk",
                        "us", "usa", "eu", "id", "ok", "am", "tv", "bi"))
# end pinned

# pinned: shared-words
# G01 (X26 step 6, Z12, X31): the words of the plugin's own shared/*.md and shared/*.txt files that are not common
# words, as reviewed when this list was last written. The harvest's stop list takes them from here, never from the
# live shared/ folder, so a client name that leaks into shared/ is not a stop word and `terms` still blocks it.
# tests/unit/test_leak_wall.py compares this list with the shipped shared/ folder; regenerate it with
# shared_vocabulary() only after `terms` over the changed shared/ has passed against the list below.
SHARED_WORDS = frozenset("""
03z 07z 1r1 1r4 20m 25k 30z 42z 45k 90k 9a a1 a11 a12 a13 a14 a16 a17 a18 a19 a2 a20 a22 a23 a24 a25 a25ddc a26 a27 a3
a38 a5 a6 a7 abandoned abc abm absence absent absolute absolutes accept acceptance accepted accepts access
accountproduct accountproductid acting activate activated activation active activities activity additional
additionalproperties additions additive address addressed adds adjacent adjustment adjustments adopt adopted adopting
adoption adopts advance adversarial advisory affecting afresh ag1 agenda agent agents aggregate agreeing agreement
agrees ai ai1 aimed alias aliased aliases alike alikes allitems allowance allowcreatereflectioncolumn allowlist
allowmultipleitems allows aloud alternative alternatives amended amendment amendments amz anchor anchors answers
anthropic api apis app appeared appearing appears append appended appendix appends application applies approver approves
approving apps arbitrary architecture archive archived archives archiving argument arithmetic array arrives artefact
artifact asc ascii asks asr assembled assert asserted asserting assertions asserts assessment assessments asset assetid
assets assigns assistant assume assumed assuming assumption assumptions async asynchronous atomic attachment attempt
attempting attempts attendees attribute attributed attributes attribution audience audit audited auditor auth author
authoring authorisation authorising authoritative authority auto automatic automationids automationspage awaits axes
axis b b1 backchannel backed background backlog backs backslash backticked backticks backup bak balance ban band bands
banner bare baseline batch batches battery bc bcalls bclients bcues bearing becoming begins behave behaviour belonged
belongs berry bespoke bill billable bind binding binds binputs bits bl blank bleed blind block blocked blockers blockids
blocking blocklist blocks blueprint bmmb bn bo boardautomation boardid boardids boardkind boardname boardrelationvalue
boards2 boards5 bold bom booked borderline bound boundaries boundary bp br bracketed breach breaking breaks brief
briefing broader broken bs bstrands budget budgeted budgets bug buildable builder building builtwithai bulk bundle
bypass bypassed byte bytes c c1 c101 c11 c2 c3 c4 c46 c4c4c4 c5 c51 c92 calculated calendar calibration callback
camelcase campaigns candidate candidates canonical cap capabilities capability capped caps capture captured cards
careless carries carrying cascade casing catalog catalogue catalogues catches categories category caution cautious
caveat caveats ceiling cell cells cent center chain chains changing channel character characters chart chat cheaper
checkable checkbox checklist checks checksum chooses chosen chunk chunks citation cite cites claim claimed claims
clarifying clash classes classic classification classified classifies classify classifying claude clause clean cleanly
cleanup clearance cleared clearing clears click clock clone closeout closes closing cloud co coarse code coerced coexist
collaborators collapsed colleague colleagues collections collide colliding collision colon color2 colors
columnvalueexception com combination comma command commas commercial commercials commit commitment commitments committed
compaction companion companions compare compared compares compete completes completion complexity compose composite
compound computed computer computes concept conclude concrete concurrency concurrent condense condensed conditions
confidence confidentiality confidently config configuration configure configured confirm confirmation confirmed confirms
conflict conflicts connect connected connecting connection connector connects consecutive consequence consistent
consolidation constant constants constraint constraints consultancy consume consumes consumption contain container
containers containment contains contamination contended content contention contents context continues contract
contradictions contradicts control controlled convenience conversation conversion convert converted converting copied
copies copy copying core corrected correcting correction corrections correctly corroborating corroboration corruption
cost costs count counted counter counting counts coverage covers cowork cr crash crashed crc32 createquestioninput
creates creating creation creationprompt creator creators credential credentials credit credits criteria criterion crlf
cross crosstalk csat cue cues currency cursor custom cutoff cygwin d d1 d11 d2 d24 d3 d5 damaged damaging dataset
datasourcelayoutconfigs date0 date2 date20 date4 date6 date8 dated db db1 dd ddthh de deactivate deactivated
deactivation deals dec decides decisions decisive default defaults defect defence deferred defers define defined
definition definitions definitive deixis delayed delete deleted deletes deletion deliberately deliverables delivered
delivery delta demo demonstrated demonstration demotes density denylist depart departed departs departure departures
dependants dependencies dependency depends deprecated depth derive derived derives desc descendant descendants
descending described describes description deserves designed desired desk despite destination destroys destructive
detect detected detection detectnativeboards detector detectors diagrams dialect died dies diff diffed differ difference
differently differs diffs digest digested digests digit digits dimension dir directly directory disabled disagree
disagreement disagrees discipline disciplined discovers discovery disk dismissed dispatch displaced display displayed
displaytype disputed disqualifies distance distinct distinctive distribution disturb dive documentation documented docx
domain dossier downgraded downstream draft drafter drafting drafts drawn drift driving dropdown drops dual dummy dumps
dup duplicate duplicateboardtype duplicated duplicates duplication duration e earliest echo echoes edge edges edit
editable edited editor edits element elements elevated eleven email1 email9 email95 embedded embeds emitted emotional
employee enabled endings enforce enforced enforces engagement enrolled ensure enter entered enters entirely entities
entitlement entity entries entry enum enumerate enumerated enumerates environment environments epoch equality equalled
equals erases error errors established estimate estimated estimates etiquette evaluate evaluated evidence ewh examples
excavated exceed exceeds exclude excluded excludes excluding exclusion exclusions exclusive execute executed executing
execution exempt exemptions exist existed existence existing exists exit expansion expectation expires expiry explicit
explicitly export exporting exports expose exposed exposes exposure express expresses expression ext extend extended
extends extensions external extract extracted extras f f1 facing facts fail failed failing fails failure fallback
falling falls false families feature featureboardview feed feeds fees fence fenced fetch fetches fewer fewest fictional
fields figures fills filter filterable filtered filtering filters finalize finance finding findings fingerprint
fingerprints finishes fire fired fires firm fit fixes fixing fixture fixtures fk flag flagged flags flagship flat
flatten flexibility flips floating floored floors flow fm fm1 focused folded folderid follower follows forbids forecast
foreseeable forgeable fork forks format formed formtoken formula formula13 formula17 formula9 formulas formulavalue
forty fourteen fraction fragment frame framing freeze freezes frequency fresh freshly frozen fully function fused g g01
g02 g03 g04 g05 g06 g07 g08 g09 g1 g10 g100 g101 g102 g103 g104 g105 g106 g107 g108 g11 g12 g13 g14 g15 g150 g151 g152
g153 g154 g155 g156 g157 g158 g159 g16 g160 g161 g162 g17 g18 g19 g2 g20 g21 g22 g23 g24 g25 g26 g27 g28 g29 g30 g31 g32
g33 g34 g35 g36 g37 g38 g39 g40 g41 g42 g43 g44 g45 g46 g47 g48 g49 g50 g51 g52 g53 g54 g55 g56 g57 g58 g59 g60 g61 g62
g63 g64 g65 g66 g67 g68 g69 g70 g71 g72 g73 g74 g75 g76 g77 g78 g79 g80 g81 g82 g83 g84 g85 g86 g87 g88 g89 g90 g91 g92
g93 g94 g95 g96 g97 g98 g99 gains gantt gap gaps gate gated gates generalised generate generated generates generation
generations generic genuine genuinely github gitignore global glossary goals gotcha gotchas governance governs gql grade
graded graders grades grammar grant grants granularity graphql grew grid grouped grouping grows guard guarded guards
guideline h h1 h2 halves handed handful handing handle handled handles handling handoff harm harvested hash hashed
hashes headed header headers heading headings headline headquarters headroom heartbeat hedge hedged helper helpers
heuristics hex hh hhmm hidden hide hides hiding hierarchy highest hit hits holder holding homophone homophones honest
honestly honoured honours hook hooks hop hops host hosted html http human hurts hybrid hyphen hyphenated hyphens
hypothesis hypothetical ib ib1 identical identification identified identifier identifiers identifies identify identity
idle ids ignore ignored ignores image images imitating imitation immediate immediately impact implausible implement
implemented implements import impossible improvise improvised inactive inaudible inbound incident incidents
includedeprecated incoming incomplete inconclusive increments incumbents indent indentation indented independence
independent independently index indistinguishable industry infer inference inferred info ingested inherit inherited
inherits init initialnumber injected injects inline inner input inputs insensitively insert inserts insights install
installation installed installs instance instances instruction instructions instrument int intake integer integration
intended intent inter interim intermediate intermediates internal interrupted interruption intersect intro introduced
introspection introspects intune invalid invalidcolumntypeexception invented inventories inventory invisible invitation
invites invoices invoke ip ir irreversible isactive itemsquerygroup itr itsm j jamf jan joined joinery joins json judge
jul k k7q2 kanban kb keeping keyed keys kinds knowledge l l1 l14 l142 l15 l17 l2 labelled lacked lacking lacks ladder
lagging landed landing lands lapses largest larkmoor lasts latest laughs layer layers lead leading leads leaf leak
leaning leanings lease leaving ledger leftover legacy legacyautomations legal legitimate legitimately length lessons
letters levels lf lies lifecycle likewise limit limited limits lineage linked linking lint linted listed listing lists
listview literal lives load loc locally location locations lock locked locks log logged logic login logo logs lone
longer lookalike lookup loop loses lower lowercase lowest lst mac machine machines maintenance malformed manage
mandatory manifest manual map mapped mapping maps margins mark markdown marked marker markers marketing marks massive
master match matchable matched matcher matchers matches matching material math matrix matters max maximum maxitems mb
mcp md meaning measure measurements measures mechanism median medium members membership memory mentioned merely merged
merges messenger meta metadata metered microsoft mid migration min minimum minted minus mirror mirrored mirroring
mirrors mirrorvalue misclassified misleading misleads mismatch misplaced misread misses missing missinglabel mix mixed
mixes mixing mk mkmcsv7h mkmvd0p6 mkrmrgz6 mm mm3gb9sn mm3jtrd mm3jtrd0 mm73h0ss mmb mmd mode model moderate modified
modifier modifiers modifies modify monotonic moving msys2 multi multiple multipliers multiply mutation mutations mutex n
n0 n10 n11 n12 n1a n1b n2 n3 n4 n5 n6 n7 n8 n9 named namespace naming narrated narration narrow narrowed narrows native
nativeness natives nearest nested nesting neutral newer newest newlines nickname nn nnn noise non nonexistent nonsense
normalisation normalised notice notifications notified notifies notify notifying noun nov null numbered numbering
numeric o object objection objections objects objectstate objecttype observation observed obtainable occur offers offset
older omit omits omitted omitting ones onward op opening operating operation operational operations opportunities
opportunity opposite opps ops option optional optionally options oracle ordered ordinal ordinary org organisation origin
original outcome outcomes output outright overflow overlay overridden override overrides oversized overview overviews
overwrite overwrites overwriting owned ownership owning owns p p1 p10 p14 p50 p90 package padded paged paging paid pain
pains pair pairs palette paragraph parameter params paraphrase parent parentfolderid parentitemid parents park parked
parking parse parsed parses parsing partial partner partway passes passing password paste patched path paths pattern
patterns pause paused payload payloads pays pdf pending people0 peoplevalue percent percentile perform performed
permanent permission permissioned permissions permitted persist personal persons personsandteams pf pf1 phonetic phrase
picks pin pinned pins pipe pitch pj pj1 pkg placed placeholder placement plain plaintext planner planted plants platform
plugin plural plus png poc pointed pointer pointers pointing poll polled pooled portal portals portfolio portfolios
positions positive positives possessive possibly practical pre precision predates predicted prefix prefixes preflight
prep prerequisites presence presented presenter presents preset pressure presumed pretooluse preview previous pricing
primitive primitives printed prints prior private privileged probability probable probe probed probes probing proceeds
produced produces products profile progress progressive projectboardid projectid promise promised promoted prompt proof
properly properties property proposal propose proposed proposes proposing prose prospect protect protected protection
protects prototype provably prove proved proven provenance proves proving provisional provisioned pub publication
publish published punctuation purple purpose py python pyyaml q q1 q2 q4 qa qi qualified qualifier qualifies quantity
quarantined quarter queries query querying queued quota quotas quoted r r0 r1 r10 r11 r12 r2 r3 r4 r5 r6 r7 r8 r9 rag
raise raised raises ramp ran random randomly range rank ranks rate ratelimit rates rating raw rc re reachable reaches
reaching reactions readable reader readiness realised reasoned rebind rebuild rebuilds rebuilt recap recapture receiver
receives recency recheck rechecked recipe recipient recipients recognises recolour recommends recomputed recon reconcile
reconciled reconciliation reconnect reconstruct reconstructable recorded recording recovery recreate recurred redact
redacted redaction redactions redone ref reference referenced references reflect reflection reflections refresh
refreshed refreshes refs refusal refuse refused refuses refusing regardless regenerated regenerates regex regexes region
register registers regular reject rejected rejection rejects rejoined relabel relabelling relate relates relation
relation21 relation6 relations relationship relative relays release released releases reliable relied remain remaining
remark remarks remembered removable removal removes rename renamed renames renaming rendered rendering renderings
renders renumber reordered rep repair repaired repairs repeat repeated repeating repeats replace replaced replacement
replaces replacing repointed repository represent reproduced requested requesting requestor require required
requirements requires research researched resembles resend resending resent reservation reserve reserved reset reshaped
residual resolvable resolve resolved resolves resolving resource resourcenotfoundexception response responses restate
restated restates resting restore restoring restrict restrictions restricts rests resume resumed resumes retained
retention retired retried retries retry retrying returned returning returns reusable reuse reused reveal revealed
reverse reviewed revise revision revisited rewrite rewrites rewritten richest rights ring rings rise risk risky roadmap
roles roll rolled rolls rollup rollups root roster rotates roughly route routes routinely routing row rows rp rubric
ruled runtime runtimes s s0 safely safety sales sample sandbox sanitised sat satellite satellites scaffolding scale
scaled scan scanned scenario scenarios schema schemas scope scoped scoping scratch screen script scripts search seat
seconds secret section sections sector seed seeded seeding seeds sees segment segments select selected selecting selects
seller semicolons sending sentence sentences sep separable separate separated separately separates separator separators
sequence sequences serial serve served server serves services serving session sessions setting settings settled settles
settling setup severity sha sha256 shaped shapes share shareable shared sharing shas shell ship shipped ships shortcut
shortens shouldcheckifstatusisnot showing sibling sides signal signals signature signatures signed silence silent
silently singleselect singular site sits sizes skills skip skipped skips sku sky sla slice slot slug slugs smaller
smallest snake snapshot snapshots softened software solution sop sorted sortedquestionslist sound source sources span
spanning spans speaker speakers speaking spec specific specifically speech spell spelled spelling spellings spells split
spoke spoken spoofable spoofing spot spots sq1 ss ssz stable stakeholder stakeholders stakes stale staleness stamp
stamped standalone standing stands starting stated statement statements states staticimage statistic statistics status95
stays stem stems stops storage store stored stores str straight strand strands stray strengths strictest strictly string
strings stripped strips strongest structural structure structured stuck style sub subagent subcommand submission
subscriber subscribers substituted subtasks succeed succeeds success successful suffix suffixed suffixes suggests suite
sum summaries summariser summary summed superseded superseding supplied supported surface surfaced surfaces surprise
survey survive survives suspect swallow swallowed sweep switch switched switches symbol symptom sync synced
synchronously syntax systems t1 tab tables tabs tactics tagged tail takeover taker target targeted targets tax technical
terminal terminologies terminology tested testing tests text text7 textf2ihoymv texts theme thinnest thirteen thread
threshold thresholds throwaway ticket tickets tidied tie tied tier tiers ties timed timeout timestamp timestamps timing
title titled titles tl token tokens tool tools topic torn touched touches tracking3 trailing trajectory transcript
transcripts transfer transient trap travel travelling travels treat treated treats trigger triggers trimmed trimming
trusted trusting ts ttp twentieth twenty twice twin txt tying typed types u u1 ui unaddressed unambiguous unanswered
unarchive unassigned unattributable unauthorized unbound unbuilt uncertain unchanged unchecked unclaimed unclear
unconfirmed unconnected undecided undeclared underscore undetectable undo undone unfiltered unintended union unique
units unknown unlock unmade unmet unordered unprepared unpriced unprobed unproved unqualified unread unreadable
unrecognized unrecorded unrecoverable unrelated unrequested unresolved unsettled unsourced unsupported untargeted
untested unverified unwired updated updatequestioninput updatequestionorder upload ups upside url urls usable usage
usedatasettemplate usemlstemplate userprofile utc utf uuid v v0 v1 v2 v3 valid validate validates validation values
vanish vanishes variable variables variant variants varied varies vary vb1 vendor verb verbally verbatim verbs verdict
verification verified verifies verify version versions versus viewer viewkind visibility visible visual vnrm
vocabularies vocabulary void voids volume vx w w1 w2 waits wakes walked walking walkthrough warn warning warnings warns
weakest wearing web webhook webhooks wedge wedges wf1 wh1 whichever whitelist whitespace widened wider widget widgets
width widths windows wins withouttitle woken won workaround workflowdraftid workflowobjectid workforms workspaceid worse
worst worth wp1 wp2 wp4 wps wrapped wrapper writer writers ws wsl x xxxx y yyyy yyyymmdd yyyymmddthhmmssffffffz z z0 za
zero zone
""".split())
# end pinned

# pinned: shared-phrases
# G04 (X26 steps 5 and 6, Z12): the capitalised runs of two to four words that the plugin's own shared/*.md and
# shared/*.txt files write, each word made of letters and a stop word (A39, R76: or a common word beside at least one
# stop word), as reviewed when this list was last written.
# A run of two or more words is dropped from a digest only when it is one of these phrases, or when every word is in
# X26's own small stop list; a shared/ word on its own no longer drops it. tests/unit/test_leak_wall.py compares this
# list with the shipped shared/ folder; regenerate it with shared_phrases() as SHARED_WORDS is regenerated.
SHARED_PHRASES = frozenset(p.strip() for p in """
a start, a tickets, a za, amz expires, api and ui, api version, b and c, b tickets, battery and gantt, c it,
calendar and gantt, call lessons, chart and battery, crlf and cr, crm and service, csat survey, csat survey and service,
d and r, d and r h, dashboard and app, dd hh, dd n, doc comments, e and crm, families b, families b and c, family e,
form and app, gantt and snapshot, group title, http put, in progress, joinery ops, larkmoor joinery,
larkmoor joinery ops, microsoft teams, mm dd, mm dd hh, mm dd n, mm ddthh, native crm, native crm and service, no api,
one json, only table, priority and planned, priority and planned timeline, probe p, products services, quotes invoices,
r a, r b, r c, r d, r d and r, r e, r f, r g, r h, r i, r j, r k, ratelimit policy, real call, real call lessons,
sales activities, sales crm, sales rep, sales targets, serial number, service contacts, service portal, service sla,
status and date, subitems and timeline, subitems of tickets, submission viewer, survey and service,
survey and service contacts, template center, the mcp, the portal, the service, the service sla, ticket id, to do,
vibe and ai, web form, where sla, word and pdf, work management, workforms submission, workforms submission viewer,
x amz, x amz expires, yyyy mm, yyyy mm dd, yyyy mm dd hh, yyyy mm dd n, yyyy mm ddthh,
yyyymmdd hhmm,
""".split(",") if p.strip())
# end pinned

# pinned: paraphrase-cues
# The six cue groups of X06. A sentence blocks when it holds a cue and a person reference: a capitalised token not
# at the sentence start and not a common word, or one of the role words. Cues are matched as normalised words.
PARAPHRASE_CUES = (
    ("assessment", ("decision maker", "the real decision maker", "approver", "gatekeeper", "blocker", "champion",
                    "skeptic", "sceptic", "veto", "influencer", "holdout", "long pole", "single point of failure",
                    "weak link", "a risk", "ally", "hostile", "resistant", "on board", "will kill it", "can kill it",
                    "signs off", "not technical", "calls the shots", "pushover", "dead weight", "deadweight",
                    "bottleneck", "troublemaker", "out of her depth", "out of his depth", "out of their depth",
                    "cant be trusted", "not senior enough")),
    ("emotional", ("burnt out", "burned out", "burnout", "stressed", "stressed out", "crying", "cried", "in tears",
                   "upset", "embarrassed", "embarrassing", "humiliated", "ashamed", "furious", "angry", "scared",
                   "frightened", "anxious", "anxiety", "keeps me up", "keeps her up", "keeps him up", "lose sleep",
                   "losing sleep", "devastated", "heartbroken", "overwhelmed", "exhausted", "miserable", "depressed",
                   "panicking", "breaking point", "fed up")),
    ("health-identity", ("hospital", "hospitalised", "hospitalized", "surgery", "illness", "sick", "sick leave",
                         "sick note", "medical leave", "maternity leave", "paternity leave", "diagnosis", "diagnosed",
                         "cancer", "pregnant", "pregnancy", "injury", "injured", "therapy", "therapist", "disability",
                         "disabled", "mental health", "rehab", "nationality", "citizenship", "immigrant",
                         "immigration", "accent", "ethnicity", "religion", "religious", "british", "scottish",
                         "welsh", "irish", "german", "spanish", "italian", "portuguese",
                         "belgian", "swiss", "austrian", "czech", "russian", "ukrainian", "romanian", "bulgarian",
                         "greek", "turkish", "indian", "pakistani", "bangladeshi", "chinese", "japanese", "korean",
                         "vietnamese", "filipino", "thai", "indonesian", "malaysian", "australian", "canadian",
                         "mexican", "brazilian", "argentinian", "colombian", "nigerian", "kenyan", "ghanaian",
                         "ethiopian", "somali", "egyptian", "moroccan", "lebanese", "iranian", "iraqi", "syrian",
                         "afghan", "israeli", "palestinian", "jamaican")),
    ("departure", ("leave the business", "leaving the business", "left the business", "leave the company",
                   "leaving the company", "left the company", "quit", "quits", "quitting", "resign", "resigns",
                   "resigning", "resignation", "retire", "retires", "retiring", "retirement", "let go", "fired",
                   "laid off", "made redundant", "redundancy", "poached", "moving on", "handing in notice",
                   "hand in notice", "notice period", "walked out")),
    ("colleague-remark", ("hates", "hate", "cant stand", "never answers", "doesnt answer", "wont answer", "ignores",
                          "useless", "lazy", "clueless", "hopeless", "disgrace", "nightmare", "menace", "careless",
                          "sloppy", "unreliable", "rude", "will kill me", "buried with", "incompetent", "a joke",
                          "idiot", "moron", "drives me mad", "drives me crazy", "cant be bothered", "two faced",
                          "backstabbing", "toxic", "difficult to work with")),
    ("personal-life", ("vacation", "holiday", "holidays", "birthday", "golf", "hangover", "hungover", "kids",
                       "children", "girlfriend", "boyfriend", "divorce", "divorced", "wedding", "honeymoon",
                       "date night", "dating")))
ROLE_WORDS = ("boss", "manager", "director", "founder", "partner", "ceo", "cfo", "coo", "cto", "vp",
              "president", "chairman", "chair", "controller", "colleague", "coworker", "co worker", "assistant",
              "receptionist", "supervisor", "mother", "father", "mum", "mom", "dad", "wife", "husband", "son",
              "daughter", "brother", "sister")
# F24: cues that ordinary process text uses about roles (an approver, a blocker, holiday cover) count only beside a
# name, never beside a role word; a role word counts only when a possessive or a name anchors it to one person.
NAME_ONLY_CUES = frozenset(("signs off", "approver", "a risk", "blocker", "holiday", "holidays"))
POSSESSIVES = frozenset(("my", "your", "his", "her", "its", "our", "their"))
PRONOUNS = frozenset(("i", "me", "my", "mine", "he", "him", "his", "she", "her", "hers", "they", "them", "their",
                      "theirs", "we", "us", "our", "ours", "you", "your", "yours", "it", "its"))
# end pinned

# pinned: internal-vocabulary
# The plugin's own words the shipped method class lacks (X06); a term finding of this class, clearable as vocabulary.
INTERNAL_VOCABULARY = ("composite block", "candidate segment", "own side stretch", "swallowed assent",
                       "boundary artifact", "shred index", "talk share", "delivery notes", "alias table",
                       "intake report", "type header", "proposed and displaced", "compound show")
# end pinned

# pinned: sales-framing
# Backlog framed as a sale (X06); a term finding of this class, clearable as vocabulary.
SALES_FRAMING = ("upsell", "up sell", "upselling", "upsell opportunity", "cross sell", "cross selling",
                 "land and expand", "expansion opportunity", "closing tactic", "closing tactics")
# end pinned

# pinned: everyday-method-rows
# R61 (the user's answer to R13): the hyphenated method rows whose spaced form is an everyday phrase. Each blocks
# only where its hyphen is written, so an agent prompt's "Never say a price" passes; every other hyphenated row
# blocks spaced as R13 built it. A unit test keeps each entry a hyphenated method row of shared/leak-terms.txt.
EVERYDAY_METHOD_ROWS = frozenset(("never-say", "not-obtainable", "cost-of-waiting", "exit-ramp"))
# end pinned

# pinned: cost-cues
# A number of the record is a cost figure when its sentence holds one of these, a currency sign or a currency code
# (X25). Rate suffixes let a payload figure of 100 to 999 (A33, R67) meet the figure rule without a cost word, a
# warning since A34 (R70). G21 (R56) adds the row labels amount, total and fuel, with their plurals; spend was
# already here.
COST_CUES = ("cost", "costs", "costed", "costing", "price", "prices", "priced", "pricing", "rate", "rates", "loaded",
             "salary", "salaries", "wage", "wages", "pay", "pays", "paid", "paying", "fee", "fees", "budget",
             "budgets", "spend", "spends", "spending", "spent", "threshold", "thresholds", "signs", "signature",
             "signatures", "sign off", "invoice", "invoices", "invoiced", "billed", "billing", "bill", "bills",
             "revenue", "revenues", "margin", "margins", "profit", "profits", "loss", "losses", "lost", "write off",
             "write offs", "written off", "credit", "credits", "refund", "refunds", "penalty", "penalties", "overrun",
             "overruns", "saving", "savings", "worth", "value", "values", "contract", "contracts", "renewal",
             "renewals", "discount", "discounts", "payback", "bleed", "upside", "hourly", "per hour", "an hour",
             "day rate", "day rates", "charge", "charges", "charged", "dollar", "dollars", "buck", "bucks", "pound",
             "pounds", "euro", "euros", "grand", "amount", "amounts", "total", "totals", "fuel", "fuels")
CURRENCY_CODES = ("usd", "gbp", "eur", "cad", "aud", "nzd", "chf")
RATE_SUFFIX = r"[ \t]?(?:/[ \t]?h(?:r|our)?\b|an[ \t]+hour\b|per[ \t]+hour\b|an[ \t]+hr\b)"
# end pinned

# pinned: confusables
# Cyrillic and Greek letters that look like Latin ones, folded before case folding (X28); dashes fold to a hyphen.
CONFUSABLES = {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
               "к": "k", "м": "m", "н": "h", "т": "t", "в": "b",
               "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
               "У": "Y", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S",
               "α": "a", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
               "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
               "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
               "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
               "−": "-", "⁄": "/"}
NARROW_SPACES = frozenset((" ", " ", " "))  # kept as one narrow space: a thousands separator
# F12: letters the first table missed (dotless i, Armenian, Cherokee capitals, Latin small capitals and a few more).
CONFUSABLES.update({"\u0131": "i", "\u0237": "j", "\u0251": "a", "\u0261": "g", "\u03c2": "c", "\u03f2": "c",
                    "\u03f3": "j", "\u04bb": "h", "\u04c0": "l", "\u04cf": "l", "\u0501": "d", "\u051b": "q",
                    "\u051d": "w", "\u0585": "o", "\u057d": "u", "\u0578": "n", "\u0570": "h", "\u0566": "q",
                    "\u0581": "g", "\u0555": "O", "\u054d": "U", "\u054f": "S"})
CONFUSABLES.update(zip("\u13a0\u13a1\u13a2\u13a5\u13a9\u13aa\u13ab\u13ac\u13b3\u13b7\u13bb\u13c0\u13c2"
                       "\u13c3\u13cf\u13d2"
                       "\u13d4\u13d5\u13d9\u13da\u13de\u13df\u13e2\u13e6\u13f4", "DRTiYAJEWMHGhZbRWSVSLCPKB"))
CONFUSABLES.update(zip("\u1d00\u0299\u1d04\u1d05\u1d07\ua730\u0262\u029c\u026a\u1d0a\u1d0b\u029f\u1d0d"
                       "\u0274\u1d0f\u1d18"
                       "\u0280\ua731\u1d1b\u1d1c\u1d20\u1d21\u028f\u1d22", "abcdefghijklmnoprstuvwyz"))
# F12: invisible characters that are not of category Cf (Default_Ignorable_Code_Point), dropped like Cf.
IGNORABLE = frozenset(["\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u3164", "\uffa0"] +
                      [chr(c) for c in range(0x180b, 0x1810)] + [chr(c) for c in range(0xfe00, 0xfe10)] +
                      [chr(c) for c in range(0xe0100, 0xe01f0)])
LINE_BREAKS = frozenset(("\u2028", "\u2029", "\x85"))  # F12: read as a line break
# G12 (X28 step 5): the shapes keyboards and word processors give an apostrophe (left quotation mark, modifier
# letter, acute accent, backtick, full-width), read as ' when a letter or digit sits on both sides.
APOSTROPHES = frozenset(("\u2018", "\u02bc", "\u00b4", "`", "\uff07"))
# G02 (X28 step 4): Latin letters with no decomposition, read as their plain spelling after case folding.
UNDECOMPOSED = {"ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ħ": "h", "ŧ": "t",
                "ı": "i", "ŀ": "l"}
# G02: the second plain reading of three of them, which the wall also tries on both sides of the hash.
ALT_READINGS = dict(UNDECOMPOSED, **{"ø": "oe", "æ": "a", "œ": "o"})
ALT_LETTERS = frozenset("øæœØÆŒ")
# end pinned

# pinned: credential-shapes
# The six shapes of X15 (with Y04's spaces around the separator), widened by the review (F10, F12). Shapes 3 and 4
# run on percent-decoded text too; shape 6 runs outside links only; every shape runs on the folded line as well. A
# credential finding is never cleared. LOOSE_SECRET and SECRET_AT_END take a value only when it looks like a secret
# (a digit, a capital inside the word, or a mark such as . @ _ /), so "the password is reset monthly" passes.
QUOTES = "\"'“”‘’"
SECRET_KEYS = (r"(?:[a-z0-9]+[_-])*(?:password|passwd|pwd|pw|pass|passphrase|passcode|secret|token|api_key|api-key|"
               r"apikey|access_key|access-key|client_secret|auth)|(?:[a-z0-9]+[_-])+key")
CREDENTIAL_SHAPES = (
    ("authorisation header", r"\b(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    ("authorisation header", r"\bauthori[sz]ation\s*[:=]\s*(?:basic|bearer|token|digest)\s+[A-Za-z0-9._~+/=-]{8,}",
     re.IGNORECASE),
    ("authorisation header", r"\b(?i:basic)\s+(?=[A-Za-z0-9+/=]*[0-9+/=]|[a-z][A-Za-z0-9+/=]*[A-Z])[A-Za-z0-9+/=]{8,}",
     0),
    ("secret pair", r"\b(?:" + SECRET_KEYS + r")[*_ \t" + QUOTES + r"]*[:=][ \t]*[" + QUOTES + r"]?[^\s" + QUOTES +
     r"]{4,}", re.IGNORECASE),
    ("url with user info", r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE),
    ("url token parameter", r"(?:\?|&)(?:[a-z0-9_.-]*(?:token|key|secret|password|passwd|pwd)|auth|signature|sig|"
                            r"code)=[^&\s#]{6,}", re.IGNORECASE),
    ("json web token", r"\beyJ[A-Za-z0-9_-]{7,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", 0),
    ("access key id", r"\bAKIA[A-Z0-9]{16}\b", 0),
    ("prefixed key", r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}", 0),
    ("repository token", r"\bgh[pousr]_[A-Za-z0-9]{36,}", 0),
    ("chat platform token", r"\bxox[abprs]-[A-Za-z0-9-]+", 0),
    ("private key", r"-----BEGIN[A-Z ]*PRIVATE KEY-----", 0),
    ("hex key", r"\b(?:[a-z0-9]+[_ -])*(?:key|token|secret|password|passwd|pwd|auth|signature)\b[^\n]{0,24}?"
                r"(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])", re.IGNORECASE))
LOOSE_KEYS = SECRET_KEYS + r"|api[ \t]key|access[ \t]key|client[ \t]secret|log[ -]?in|credentials?|key"
LOOSE_SECRET = (r"\b(?:" + LOOSE_KEYS + r")[*_ \t" + QUOTES + r"]*(?:[:=|]|[ \t]+(?:is|was)\b)[ \t]*[" + QUOTES +
                r"]?(?P<value>[^\s|" + QUOTES + r"]{4,})")
SECRET_AT_END = r"\b(?:" + LOOSE_KEYS + r")[*_ \t" + QUOTES + r"]*[:=][ \t]*$"
LONG_SECRET = r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])"
# end pinned

# pinned: internal-notes
# The marks of the record's own internal files (X40, Y07). An internal-note finding is never cleared, except one of
# CLEARABLE_NOTES, which an ok row of the strand's own allowlist clears to a caution (R62, the user's answer to R17).
INTERNAL_NOTE_PHRASES = ("internal: never client-facing", "never client-facing", "internal only", "not for the client",
                         "note to self", "not client-facing", "internal use only", "not for clients")  # last three: F18
CLEARABLE_NOTES = frozenset(("internal only", "internal use only", "not for clients"))  # normal forms (X28)
FRONT_MATTER_LINE = r"^[a-z][a-z0-9_-]*:[ \t]*[\"“”][^\"“”\n]*[\"“”]"
SPEAKER_LABEL = r"\bspeaker[ \t_]*(?:\d+\b|[a-z](?=[ \t]*[:)\]]))"  # F18: SPEAKER_00 and Speaker A: as well
# end pinned

# pinned: structural-id-keys
# Y08: a digit-only value directly under one of these keys is a monday id, not text. tests/unit/test_leak_fixture.py
# holds a copy, and a unit test keeps the two equal.
STRUCTURAL_ID_KEYS = frozenset("""
id ids account_id workspace_id workspace_ids workspaceId workspaceIds folder_id folder_ids folderId board_id board_ids
boardId boardIds group_id groupId item_id item_ids itemId itemIds parent_id parentId parent_item_id doc_id docId
object_id objectId view_id viewId dashboard_id dashboardId widget_id widgetId automation_id automationId workflow_id
workflowId agent_id agentId app_id appId user_id user_ids userId userIds team_id team_ids teamId teamIds owner_ids
subscriber_ids
""".split())
# end pinned

PLUGIN = Path(__file__).resolve().parent.parent
KEYS = ("file", "field", "problem", "expected")
WHOLE = mc.WHOLE_FILE
MB = 1024 * 1024
TEXT_LIMIT, PAYLOAD_LIMIT, DEPTH_LIMIT = 20 * MB, 20 * MB, 64
DOCX_MEMBER_LIMIT, DOCX_TOTAL_LIMIT, DOCX_RATIO, DOCX_RATIO_FLOOR = 50 * MB, 200 * MB, 100, 1 * MB
LINE_WINDOW, LINE_OVERLAP = 10000, 200
RUN_WORDS, NEAR_WORDS, QUOTE_WORDS = 6, 8, 8
MATCH_CUT = 80
TEXT_EXT, SCAN_EXT, SYSTEM_FILES = (".md", ".txt", ".docx"), (".md", ".txt", ".docx", ".json"), \
    frozenset((".ds_store", "thumbs.db", "desktop.ini"))
SHIPPED_NAME, SETTINGS_NAME, LOCAL_NAME = "<plugin>/shared/leak-terms.txt", "<home>/local/settings.json", \
    "<home>/local/leak-terms.txt"
ID_ROW = r"(?<![\w/=?&#.-])\d{8,}(?![\w-])"  # the eight-digit monday id row of id-patterns, the one that skips links
ID_WIDE = re.compile(r"(?<![^\W_])\d{8,}(?![^\W_])")  # the same row beside any mark once real links are masked (Z03)
CLASS_NAME = re.compile(r"[A-Za-z0-9-]+")
NESTED = re.compile(r"\((?:[^()\\]|\\.)*(?:[*+]|\{\d*,\d*\})(?:[^()\\]|\\.)*\)(?:[*+]|\{\d*,?\d*\})")
GAP = r"[\s,.\-_/|·]+"
HYPHEN_GAP = r"[\s,.]*[\-_/|·][\s,.\-_/|·]*"  # R61: a gap that holds a hyphen or another joining mark
LEGAL_SUFFIXES = frozenset(("inc", "incorporated", "llc", "ltd", "limited", "plc", "gmbh", "corp", "corporation", "co",
                            "company", "lp", "llp", "sa", "ag", "bv", "nv", "pty", "pte", "srl", "oy", "ab"))  # X28 step 6
WORDCHAR = r"[^\W_]"
TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
POSSESSIVE = re.compile(r"['’]s$")
# F25: a full stop after e.g., i.e., etc., vs. or approx. does not end a sentence, for every rule that reads
# sentences (the cost cue of a number, the paraphrase rule); R64 keeps it after dropping the tool-category check.
SENTENCE_END = re.compile(r"(?:(?<!\be\.g)(?<!\bi\.e)(?<!\betc)(?<!\bvs)(?<!\bapprox)\.|!|\?)(?=\s|$)|\n",
                          re.IGNORECASE)
QUOTE_SPANS = re.compile(r"(?:\"|“|”)([^\"“”\n]+)(?:\"|“|”)")
LOCATION = re.compile(r"@\d{2}:\d{2}:\d{2}\b|\bcues? \d+(?:-\d+)?\b|\bL\d{2,4}(?:-\d{1,4})?\b", re.IGNORECASE)
LINKS = (re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)"),
         re.compile(r"\b(?:href|src)\s*=\s*(?:\"|')([^\"']*)(?:\"|')", re.IGNORECASE),
         re.compile(r"<((?:https?://|mailto:)[^>\s]+)>", re.IGNORECASE),
         re.compile(r"(?<![\w/])((?:https?://|mailto:)[^\s)\]>,|]+)", re.IGNORECASE))  # F32: no comma or pipe
SCHEMED = re.compile(r"(?:https?://|mailto:)", re.IGNORECASE)
# R63 (R27 widened): a web address with no scheme whose host ends in .com and a slash is a link for the id row's mask.
# Its labels are letters, digits and hyphens; it stops where a bare URL stops.
COM_ADDRESS = re.compile(r"(?<![\w.@/:%-])(?:[A-Za-z0-9-]+\.)+com/[^\s)\]>,|]*", re.IGNORECASE)
PERCENT = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SECTION_NUMBER = re.compile(r"(\d{1,2})(?:[.):\s]|$)")  # G18: `## 4)` and `## 4:` are section 4 too
CLIENT_SECTIONS = tuple(range(1, 16))  # X09: the blueprint's client-facing sections; 16, Internal, is last (D19)
# R52: the blueprint template's own section titles, as the guide numbers the sixteen. They are plugin vocabulary,
# so a heading whose title is its section's own (letter case and marks aside) is never checked as client text.
SECTION_TITLES = ("Version scope and deferred items", "Product fit", "Requirement trace", "Structure mapping", "Forks",
                  "Live objects this strand touches", "Workspace and product binding", "Native-entity map",
                  "Portfolio and project plan", "Board inventory", "Columns, relations and mirrors",
                  "Groups, views, forms, docs, dashboards", "The lists",
                  "Permissions, ownership, plan tier and data policy",
                  "Irreversible operations, UI steps and client decisions", "Internal")
SCHEMA_LINE = re.compile(r"^\s*schema\s*:\s*[\"'\u201c\u201d\u2018\u2019]?\s*(.*?)\s*"
                         r"[\"'\u201c\u201d\u2018\u2019]?\s*$", re.IGNORECASE)  # F03: quoted or not
SNAPSHOT_SCHEMA = re.compile(r"document-summary/(\d+)")
STRUCTURAL_VALUE = re.compile(r"[1-9][0-9]*")
# A33 (R66): a key that names a monday id is structural whatever the tool calls it, beside the pinned list: `id` or
# `ids` alone, any key ending `_id` or `_ids`, and a camel-case key ending `Id`, `ID`, `Ids` or `IDs` after a
# lower-case letter or a digit (parentFolderId, accountProductId), each in any case. A word that merely ends in the
# letters, such as `paid`, `valid` or `grid`, is not one.
ID_KEY = re.compile(r"(?:.*_)?[iI][dD][sS]?|.*[a-z0-9]I[dD][sS]?")
# A33 (R67): a number below this is a count, a label or a step, never a client figure, in digits or in words, on
# both sides: the record's figures F (X25) and the checked text. Percentages keep their own rule.
SMALL_FIGURE = 100
# A34 (R70): a client's own cost figure (of SMALL_FIGURE or more) or cost percentage, met in its own build (scan,
# payload, blueprint, sample rows too), warns instead of blocking, in every form the figure rules read, so the write
# goes ahead and the user sees it. The client's exclusions, at any value, and other clients' figures (the wall) block.
OWN_FIGURE_EXPECTED = "check the client's own figure is meant for their build; it is reported and kept"
# A39 (R75): a phone column's value is digits, often eight or more, and not an id. monday takes it keyed by the
# column's id inside column_values (create_item, change_item_column_values, an item batch), as an object of the
# digits and a two-letter country code or as a string of the digits and, after a space, the code. Both the place
# and the shape are needed: the column id (phone, lead_phone, contact_phone, phone_mm8k2q4z) says what the column
# is, and the shape says the value is a number to dial, so a sentence or another key there keeps every rule.
COLUMN_VALUES = frozenset(("columnvalues",))  # column_values or columnValues, read without underscores or case
PHONE_COLUMN = re.compile(r"(?:[a-z]+_)?phone(?:\d+|_{1,2}[a-z0-9]+)?")
PHONE_DIGITS = re.compile(r"\+?\d{4,15}")  # at most fifteen digits, as an international number has
PHONE_TEXT = re.compile(r"\+?\d{4,15}(?:[ \t][A-Za-z]{2})?")
COUNTRY_CODE = re.compile(r"[A-Za-z]{2}")
# A39 (R77): a status or dropdown column's settings (columnSettings, settings, settings_str or defaults, as an
# object or a string of JSON) hold a list of labels whose colour, index and position are numbers of monday's, not
# the record's, so they raise no number warning; the label's own text is read as before.
SETTINGS_KEYS = frozenset(("columnsettings", "settings", "settingsstr", "defaults"))
LABEL_LISTS = frozenset(("labels",))
LABEL_NUMBER_KEYS = frozenset(("color", "index", "position"))


# The frame (a copy of ledger.py's, nod 2 and W91): the envelope, the refusal helper, the parser.

class Usage(Exception):
    """A usage error: exit 3 with the JSON envelope, never argparse's own exit 2 (G10)."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


def emit(data):
    """Print one JSON object as UTF-8 with LF: the same bytes on every system."""
    text = mc.json_text(data)
    sys.stdout.flush()
    raw = getattr(sys.stdout, "buffer", None)
    if raw is None:
        sys.stdout.write(text)
    else:
        raw.write(text.encode("utf-8"))
        raw.flush()


def cannot(file, field, problem, expected):
    """The could-not-run stop (exit 3), one (file, field, problem, expected) finding."""
    return mc.CannotRun((file, field, problem, expected))


def read_bytes(path):
    """Every file the lint reads goes through here, so a failed read is one place (L207)."""
    with open(str(path), "rb") as handle:
        return handle.read()


# Text: folding with a map back to the original, tokens, sentences and paragraphs (X24, X28).

class Variant:
    """A copy of a text with, for each of its characters, the offset of the original character it came from."""
    __slots__ = ("text", "offsets")

    def __init__(self, text, offsets):
        self.text, self.offsets = text, offsets

    def span(self, start, end):
        """The original (start, end) of this copy's [start, end)."""
        if not self.offsets:
            return 0, 0
        start = min(start, len(self.offsets) - 1)
        first = self.offsets[start]
        last = self.offsets[max(start, min(end, len(self.offsets)) - 1)] + 1
        return first, max(first, last)


def plain(text, base=0):
    return Variant(text, list(range(base, base + len(text))))


def fold(text, offsets=None, alt=False):
    """X28 steps 1 to 4: format characters removed, NFKC, look-alikes folded, case folded, diacritics dropped, and
    the letters with no decomposition spelt plain (G02; with alt, the second reading of ø, æ and œ)."""
    plainly = ALT_READINGS if alt else UNDECOMPOSED
    out, where, last = [], [], len(text) - 1
    for index, char in enumerate(text):
        origin = offsets[index] if offsets is not None else index
        if char in APOSTROPHES and 0 < index < last and text[index - 1].isalnum() and text[index + 1].isalnum():
            out.append("'")  # G12: an apostrophe shape inside a word, before NFKC turns the accent into a space
            where.append(origin)
            continue
        if char < "\x80":
            out.append(char.lower())
            where.append(origin)
            continue
        if char in NARROW_SPACES:
            out.append(" ")
            where.append(origin)
            continue
        if unicodedata.category(char) == "Cf" or char in IGNORABLE:
            continue
        if char in LINE_BREAKS:
            out.append("\n")
            where.append(origin)
            continue
        for part in unicodedata.normalize("NFKC", char):
            if part in IGNORABLE:
                continue
            part = CONFUSABLES.get(part, part)
            for piece in unicodedata.normalize("NFD", part.casefold()):
                if unicodedata.category(piece) != "Mn":
                    for letter in plainly.get(piece, piece):
                        out.append(letter)
                        where.append(origin)
    return Variant("".join(out), where)


def has_alt(text):
    """G02: the text holds a letter with a second plain reading, so the wall also reads it that way."""
    return not text.isascii() and any(c in ALT_LETTERS for c in text)


def fold_variant(variant):
    folded = fold(variant.text)
    return Variant(folded.text, [variant.offsets[i] for i in folded.offsets])


def fold_text(text):
    return fold(text).text


def percent_decode(variant):
    """A copy with every run of %XX escapes decoded as UTF-8 (X03), mapped back to the original."""
    out, where, last = [], [], 0
    for match in PERCENT.finditer(variant.text):
        out.append(variant.text[last:match.start()])
        where.extend(variant.offsets[last:match.start()])
        decoded = bytes(int(match.group()[i + 1:i + 3], 16) for i in range(0, len(match.group()), 3))
        piece = decoded.decode("utf-8", errors="replace")
        out.append(piece)
        where.extend([variant.offsets[match.start()]] * len(piece))
        last = match.end()
    out.append(variant.text[last:])
    where.extend(variant.offsets[last:])
    return Variant("".join(out), where)


def percent_decode_all(variant, rounds=3):
    """F41: percent-decoding repeated while it changes the text (a double encoding such as %252F), a few rounds."""
    for _ in range(rounds):
        decoded = percent_decode(variant)
        if decoded.text == variant.text:
            break
        variant = decoded
    return variant


def front_matter_schema(lines, index, reach=40):
    """F18 (X40, Y07): the `---` line at `index` opens a block that holds a `schema:` line before its closing `---`."""
    for _, line in lines[index + 1:index + 1 + reach]:
        if line.strip() == "---":
            return False
        if line.strip().lower().startswith("schema:"):
            return True
    return False


def slashed(variant):
    return Variant(variant.text.replace("\\", "/"), variant.offsets)


def words_of(text, alt=False):
    """The normalised words of a text (X24): folded, possessive dropped, apostrophes removed."""
    found = []
    for match in TOKEN.finditer(fold(text, alt=alt).text):
        word = POSSESSIVE.sub("", match.group()) if len(match.group()) > 2 else match.group()
        word = word.replace("'", "").replace("’", "")
        if word:
            found.append(word)
    return found


def normal_form(text):
    """The spaced normal form X28 compares: the words joined by one space."""
    return " ".join(words_of(text))


class Token:
    __slots__ = ("word", "fstart", "fend", "start", "end", "cap", "upper", "sentence", "paragraph", "first")

    def __init__(self, word, fstart, fend, start, end, cap, upper):
        self.word, self.fstart, self.fend, self.start, self.end = word, fstart, fend, start, end
        self.cap, self.upper, self.sentence, self.paragraph, self.first = cap, upper, 0, 0, False


def sentence_spans(text):
    """A sentence ends at . ! or ? before whitespace or the end, and at every line break (X12's reading, which the
    cost cue and the paraphrase rule keep, R64)."""
    spans, start = [], 0
    for match in SENTENCE_END.finditer(text):
        spans.append((start, match.end()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def paragraph_spans(text):
    """Blocks of lines between blank lines; a heading is a paragraph of its own (X12's reading, which the
    phonetic windows keep, R64)."""
    spans, start, end, position = [], None, None, 0
    for line in text.split("\n"):
        line_start, line_end = position, position + len(line)
        position = line_end + 1
        if not line.strip() or line.lstrip().startswith("#"):
            if start is not None:
                spans.append((start, end))
                start = None
            if line.strip():
                spans.append((line_start, line_end))
            continue
        if start is None:
            start = line_start
        end = line_end
    if start is not None:
        spans.append((start, end))
    return spans


def tokenise(original, folded):
    """Tokens of a folded copy, each with its original span, its case and its sentence and paragraph."""
    sentences = sentence_spans(folded.text)
    paragraphs = paragraph_spans(folded.text)
    s_starts, p_starts = [s for s, _ in sentences], [s for s, _ in paragraphs]
    tokens, last_sentence = [], None
    for match in TOKEN.finditer(folded.text):
        raw = match.group()
        word = POSSESSIVE.sub("", raw) if len(raw) > 2 else raw
        word = word.replace("'", "").replace("’", "")
        if not word:
            continue
        start, end = folded.span(match.start(), match.end())
        shown = original[start:end]
        token = Token(word, match.start(), match.end(), start, end, shown[:1].isupper(),
                      shown.isupper() and any(c.isalpha() for c in shown))
        token.sentence = max(0, bisect.bisect_right(s_starts, match.start()) - 1)
        token.paragraph = max(0, bisect.bisect_right(p_starts, match.start()) - 1)
        token.first = token.sentence != last_sentence
        last_sentence = token.sentence
        tokens.append(token)
    return tokens


def link_spans(text):
    """The targets of Markdown links and images, href and src values, autolinks and bare URLs (X34)."""
    spans = []
    for pattern in LINKS:
        for match in pattern.finditer(text):
            spans.append((match.start(1), match.end(1)))
    return sorted(spans)


def real_links(text):
    """F31 (X34, Z03): the link targets that start with a scheme the bare-URL form names; a relative Markdown target
    such as boards/<id> only looks like a link, so its id blocks. R63: a web address with no scheme whose host ends
    in .com and a slash (example.com/page/<id>) counts too, from its host to where a bare URL stops."""
    spans = [(s, e) for s, e in link_spans(text) if SCHEMED.match(text, s)]
    return sorted(spans + [match.span() for match in COM_ADDRESS.finditer(text)])


def inside(spans, start, end):
    return any(s <= start and end <= e for s, e in spans)


def mask(text, spans):
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def token_matches(tokens, forms):
    """F11 (X24, X28): (start, end) in the original text of every run of consecutive tokens that spells one of the
    word forms, whatever marks sit between the words (emphasis, brackets, a colon, a possessive)."""
    found = []
    if not forms or not tokens:
        return found
    for form in forms:
        size = len(form)
        for i in range(len(tokens) - size + 1):
            if tokens[i].word == form[0] and all(tokens[i + k].word == form[k] for k in range(1, size)):
                found.append((tokens[i].start, tokens[i + size - 1].end))
    return found


def literal_regex(term, tokenised=False, fused=False, spaced=True):
    """A literal row as a pattern on folded text: boundaries of LT:18, the gaps of X32, and the fused form. With
    spaced false, a hyphenated row needs a joining mark wherever the row has its hyphen (R61)."""
    folded = fold_text(term)
    hyphenated = re.fullmatch(r"[^\W_]+(?:[\s.-]+[^\W_]+)*", folded.strip()) and re.search(r"[^\W_]-[^\W_]", folded)
    words = words_of(term) if tokenised or hyphenated else folded.split()  # F13: a hyphen is a gap (X24, X32)
    if not words:
        return None
    gaps = [GAP] * (len(words) - 1)
    joints = re.findall(r"[\s.-]+", folded.strip()) if hyphenated and not spaced else []
    if len(joints) == len(gaps):
        gaps = [HYPHEN_GAP if "-" in joint else GAP for joint in joints]
    apostrophe = "'" in folded or "’" in folded

    def piece(word):
        if tokenised and apostrophe:
            return "['’]?".join(re.escape(c) for c in word)
        return re.escape(word)

    forms = [words]
    if tokenised:
        bare = list(words)
        while len(bare) > 1 and bare[-1] in LEGAL_SUFFIXES:
            bare.pop()
        if bare != words:
            forms.append(bare)
    alternatives = []
    for form in forms:
        joined = piece(form[0]) + "".join(gap + piece(word) for gap, word in zip(gaps, form[1:]))
        alternatives.append(joined)
        if fused and len(form) > 1:
            alternatives.append(re.escape("".join(form)))
    # F07: a boundary only on a side where the term has a word character, so "overloaded[I]" holds the marker [I].
    head = "(?<!%s)" % WORDCHAR if re.match(WORDCHAR, words[0][:1]) else ""
    tail = "(?!%s)" % WORDCHAR if re.match(WORDCHAR, words[-1][-1:]) else ""
    return re.compile(r"%s(?:%s)%s" % (head, "|".join(alternatives), tail))


def cut(text):
    text = " ".join(text.split())
    return text if len(text) <= MATCH_CUT else text[:MATCH_CUT - 1] + "…"


# The phonetic key and the edit distance (X32, Y09).

VOWELS = frozenset("aeiou")
PHONE_MAP = {"b": "P", "p": "P", "f": "F", "k": "K", "g": "K", "j": "J", "s": "S", "t": "T", "d": "T", "l": "L",
             "m": "M", "n": "M", "r": "R", "X": "X", "0": "0"}
FIRST_KEEP = {"w": "W", "h": "H", "y": "Y"}


def phonetic_key(word):
    """The key of one word: X32's rewrites, the symbol map, the first letter kept, runs collapsed."""
    w = "".join(c for c in fold_text(word) if "a" <= c <= "z")
    if not w:
        return ""
    for head, new in (("kn", "n"), ("gn", "n"), ("pn", "n"), ("wr", "r"), ("ps", "s"), ("wh", "w")):
        if w.startswith(head):
            w = new + w[2:]
            break
    else:
        if w.startswith("x"):
            w = "s" + w[1:]
    phones, i, n = [], 0, len(w)
    while i < n:
        c, two, three = w[i], w[i:i + 2], w[i:i + 3]
        after = w[i + 1] if i + 1 < n else ""
        if two == "ph":
            phones.append("f"); i += 2; continue  # noqa: E702
        if two == "ck":
            phones.append("k"); i += 2; continue  # noqa: E702
        if three == "sch":
            phones.extend("sk"); i += 3; continue  # noqa: E702
        if three == "tch":
            phones.append("X"); i += 3; continue  # noqa: E702
        if two in ("ch", "sh"):
            phones.append("X"); i += 2; continue  # noqa: E702
        if two == "th":
            phones.append("0"); i += 2; continue  # noqa: E702
        if two == "dg":
            phones.append("j"); i += 2; continue  # noqa: E702
        if two == "qu":
            phones.extend("kw"); i += 2; continue  # noqa: E702
        if c == "x":
            phones.extend("ks"); i += 1; continue  # noqa: E702
        if two == "gh" and (i + 2 >= n or w[i + 2] not in VOWELS):
            i += 2
            continue
        if c == "c":
            phones.append("s" if after and after in "eiy" else "k")
        elif c == "g":
            phones.append("j" if after and after in "eiy" else "g")
        else:
            phones.append({"q": "k", "z": "s", "v": "f"}.get(c, c))
        i += 1
    out = []
    for index, phone in enumerate(phones):
        if index == 0 and (phone in VOWELS or phone in FIRST_KEEP):
            out.append("A" if phone in VOWELS else FIRST_KEEP[phone])
        elif phone in PHONE_MAP:
            out.append(PHONE_MAP[phone])
    key = []
    for symbol in out:
        if not key or key[-1] != symbol:
            key.append(symbol)
    return "".join(key)


def letters(word):
    return "".join(c for c in fold_text(word) if "a" <= c <= "z")


def ordinary(word):
    """A36 (R72): an everyday word for the firm's phonetic rule: a common word or a stop word, or the plural of a
    common word (R43 reads a plural as its singular)."""
    return word in COMMON_WORDS or word in STOP_WORDS or any(stem in COMMON_WORDS for stem in plural_stems(word))


def edit_distance(a, b, limit):
    """Damerau-Levenshtein distance (adjacent transpositions), or limit + 1 once it is past the limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous2, previous = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if previous2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], previous2[j - 2] + 1)
        if min(current) > limit:
            return limit + 1
        previous2, previous = previous, current
    return previous[len(b)]


class PhoneticSource:
    """One source of the phonetic rule: its words, keys and letters, and its whitelist rows."""

    def __init__(self, cls, term, origin, whitelist):
        self.cls, self.term, self.origin, self.whitelist = cls, term, origin, whitelist
        self.words = words_of(term)
        keys = [phonetic_key(w) for w in self.words]
        self.letters = "".join(letters(w) for w in self.words)
        self.keys = {" ".join(keys), "".join(keys), phonetic_key(self.letters)} - {""}
        heard = [w.replace("th", "t").replace("ph", "p") for w in (letters(w) for w in self.words)]
        if heard != [letters(w) for w in self.words]:  # F17: a th heard as t (and ph as p) is a second key
            second = [phonetic_key(w) for w in heard]
            self.keys |= {" ".join(second), "".join(second), phonetic_key("".join(heard))} - {""}
        size = len(self.letters)
        self.limit = 0 if size < 5 else (1 if size <= 7 else 2)


# The run: the record, the home, every input read with its hash, and the findings (X16, X41).

class Run:
    """One command's state. Inputs are recorded as they are read, so the output names every byte judged."""

    def __init__(self, command, args):
        self.command, self.args = command, args
        self.root = self.home = None
        self.inputs, self.findings, self.error = {}, [], None
        self.mode, self.strand, self.args_digest = None, None, None
        self.lists = self.sets = None
        self.allowlists, self.exclusions = {}, None
        self.texts = self.wall = self.stop = None
        self.plans = {}  # A36 (R73): each strand's frozen revision as planned values, read on first use
        self.record, self.extra = True, {}
        self.spans = bool(getattr(args, "spans", False))
        self.order = 0

    def locate(self):
        """The record as record.py and ledger.py locate it (W91): --record, else the current folder."""
        root = Path(self.args.record) if self.args.record else Path.cwd()
        if not (root / "CLIENT.md").is_file():
            raise cannot("CLIENT.md", "record", "no CLIENT.md in the folder %s" % root.name,
                         "a client folder holding CLIENT.md, or --record <folder>")
        self.root, self.home = root.resolve(), mc.home()

    def name(self, path):
        """A record-relative POSIX name, or <home>/... for a file under the home outside the record."""
        resolved = Path(os.path.abspath(str(path)))
        for base, prefix in ((self.root, ""), (Path(os.path.abspath(str(self.home))), "<home>/")):
            try:
                return prefix + resolved.relative_to(base).as_posix()
            except ValueError:
                continue
        return resolved.as_posix()

    def read(self, path, name, limit=None):
        """The bytes of one input, its hash recorded; unreadable or over the limit is exit 3."""
        limit = TEXT_LIMIT if limit is None else limit
        try:
            size = os.path.getsize(str(path))
        except OSError as exc:
            raise cannot(name, WHOLE, "cannot read the file: %s" % exc, "a readable file")
        if size > limit:
            raise cannot(name, WHOLE, "the file is %d bytes, over the %d-byte limit" % (size, limit),
                         "a smaller file, or the text split into several")
        try:
            data = read_bytes(path)
        except OSError as exc:
            raise cannot(name, WHOLE, "cannot read the file: %s" % exc, "a readable file")
        self.inputs[name] = {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
        return data

    def text(self, path, name):
        """Decoded UTF-8 text, a leading byte-order mark dropped, line endings read as LF (G11)."""
        return decode(self.read(path, name), name)[0]

    def absent(self, name):
        self.inputs.setdefault(name, {"file": name, "state": "absent"})

    def add(self, finding):
        self.order += 1
        finding["_order"] = finding.get("_order", (9, finding["file"], 0, 0, self.order))
        self.findings.append(finding)


def decode(data, name):
    """(LF text, raw offsets): the decoded text with CRLF and CR read as LF, and each character's offset in the
    decoded text as stored, so a span names the file's own characters (X23)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise cannot(name, WHOLE, "the file is not UTF-8: %s" % exc, "a UTF-8 text file")
    if "\r" not in text and not any(c in text for c in LINE_BREAKS):
        return text, None
    out, raw, i = [], [], 0
    while i < len(text):
        if text[i] in LINE_BREAKS:  # F12: a line or paragraph separator reads as a line break
            out.append("\n")
            raw.append(i)
            i += 1
            continue
        if text[i] == "\r":
            out.append("\n")
            raw.append(i)
            i += 2 if text[i + 1:i + 2] == "\n" else 1
            continue
        out.append(text[i])
        raw.append(i)
        i += 1
    return "".join(out), raw


# G20 (R54): the one strict JSON reader, in mmb_common (R55): a key written twice in one object raises RepeatedKey
# (path, key), X22's path to the key; json_value below and the payload walk use it.
RepeatedKey, key_path, strict_json = mc.RepeatedKey, mc.key_path, mc.strict_json


def repeated(name, exc, expected):
    path, key = exc.args
    return cannot(name, path, "the key %s is written twice in one object, so what the file says depends on the "
                  "program that reads it" % json.dumps(key, ensure_ascii=False), expected)


ONCE_SETTINGS = "each key written once in its object, as record.py home init writes it"
ONCE_PAYLOAD = "each key written once in its object, as the tool will receive it"


def json_value(text, name, once=ONCE_SETTINGS):
    """One JSON value, read strictly (F39, G20): a key written twice in one object is exit 3 on its path."""
    try:
        return strict_json(text)
    except RepeatedKey as exc:
        raise repeated(name, exc, once)
    except ValueError as exc:
        raise cannot(name, WHOLE, "not valid JSON: %s" % exc, "a JSON value")


# The lists: the shipped list, the local list, the settings' firm and account structure (X04, X33, nod 8).

class Row:
    __slots__ = ("kind", "cls", "term", "line", "list", "regex", "parent")

    def __init__(self, kind, cls, term, line, source, regex=None, parent=None):
        self.kind, self.cls, self.term, self.line, self.list = kind, cls, term, line, source
        self.regex, self.parent = regex, parent

    def where(self):
        return "%s line %d" % (self.list, self.line)


def parse_list(text, name, local):
    """Rows of the leak-terms syntax (LT:17 to 29) with X33's rules; anything it cannot apply is exit 3."""
    rows, cls, phonetic = [], None, None
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        field = "line %d" % number
        if not line or line.startswith("#"):
            continue
        if line.startswith("class:"):
            cls = line[6:].strip()
            if not CLASS_NAME.fullmatch(cls):
                raise cannot(name, field, "the class name %r is not letters, digits and hyphens" % cls,
                             "class: <name>, the name in letters, digits and hyphens")
            phonetic = None
            continue
        if cls is None and not local:
            raise cannot(name, field, "a row above the first class line", "every row of the shipped list under a "
                         "class: line")
        row_cls = cls or LOCAL_CLASS
        if line.startswith("re:"):
            pattern = line[3:].strip()
            if not pattern:
                raise cannot(name, field, "a re: row with no pattern", "re: <a Python regular expression>")
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise cannot(name, field, "the pattern does not compile: %s" % exc, "a Python regular expression")
            if local and (NESTED.search(pattern) or risky_pattern(pattern)):
                raise cannot(name, field, "a pattern that can run for a very long time (a repeated group that holds "
                             "a repeat or an alternation)", "a pattern without a repeated group that itself repeats")
            rows.append(Row("re", row_cls, pattern, number, name, regex=regex))
            phonetic = None
        elif line.startswith("phonetic:"):
            term = line[9:].strip()
            if not words_of(term):
                raise cannot(name, field, "a phonetic: row with no term", "phonetic: <term>")
            phonetic = Row("phonetic", row_cls, term, number, name)
            rows.append(phonetic)
        elif line.startswith("whitelist:"):
            term = line[10:].strip()
            if not words_of(term):
                raise cannot(name, field, "a whitelist: row with no term", "whitelist: <term>")
            if row_cls != "firm" and phonetic is None:
                raise cannot(name, field, "a whitelist: row with no phonetic: row directly above it",
                             "a whitelist: row under the phonetic: row whose legitimate use it names")
            rows.append(Row("whitelist", row_cls, term, number, name, parent=None if row_cls == "firm" else phonetic))
        else:
            rows.append(Row("literal", row_cls, line, number, name))
            phonetic = None
    return rows


def risky_pattern(pattern):
    """F21 (X33, X42): True when a repeat of the parsed pattern holds, at any depth, a repeat of variable length or
    an alternation, as (a|aa)+ and (?:(?:a+))+ do. The standard parser is re._parser from 3.11, sre_parse before."""
    try:
        from re import _parser as parser
    except ImportError:  # Python 3.9 and 3.10
        import sre_parse as parser

    def subs(op, av):
        name = str(op)
        if name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            return [av[2]]
        if name == "SUBPATTERN":
            return [av[-1]]
        if name == "ATOMIC_GROUP":
            return [av]
        if name in ("ASSERT", "ASSERT_NOT"):
            return [av[1]]
        if name == "BRANCH":
            return list(av[1])
        if name == "GROUPREF_EXISTS":
            return [p for p in av[1:] if p is not None]
        return []

    def variable(tree):
        for op, av in tree:
            name = str(op)
            if name == "BRANCH" or (name.endswith("REPEAT") and av[0] != av[1]):
                return True
            if any(variable(sub) for sub in subs(op, av)):
                return True
        return False

    def risky(tree):
        for op, av in tree:
            if str(op).endswith("REPEAT") and av[1] > 1 and variable(av[2]):
                return True
            if any(risky(sub) for sub in subs(op, av)):
                return True
        return False

    return risky(parser.parse(pattern, re.IGNORECASE))


class Pattern:
    """One compiled literal: its rule, class and the row it came from.
    A tokenised row (the firm, the plugin, the seller's names, the exclusions) also keeps its word forms of two
    words or more, matched on the token stream so that no mark between the words breaks the match (F11)."""
    __slots__ = ("rule", "cls", "regex", "origin", "term", "forms")

    def __init__(self, rule, cls, regex, origin, term, tokenised=False):
        self.rule, self.cls, self.regex, self.origin, self.term = rule, cls, regex, origin, term
        self.forms = token_forms(term) if tokenised else []


def token_forms(term):
    """The word forms of a term of two words or more, with and without its trailing legal suffixes (X28, Z11)."""
    words, forms = words_of(term), []
    while len(words) >= 2:
        forms.append(tuple(words))
        if words[-1] not in LEGAL_SUFFIXES:
            break
        words = words[:-1]
    return forms


FUSED_CLASSES = ("firm", "plugin")


class Lists:
    """Everything the term rules read: the literal and re: rows of both lists, the firm's renderings and phonetic
    sources, the seller's own account structure, and the embedded vocabulary groups."""

    def __init__(self, rows, settings):
        self.rows, self.literals, self.regexes, self.phonetic, self.id_row = rows, [], [], [], None
        self.firm_whitelist = [row.term for row in rows if row.kind == "whitelist" and row.cls == "firm"]
        for row in rows:
            fused = row.cls in FUSED_CLASSES
            if row.kind in ("literal", "phonetic"):
                everyday = row.cls == "method" and row.term.strip().lower() in EVERYDAY_METHOD_ROWS  # R61
                regex = literal_regex(row.term, tokenised=fused, fused=fused, spaced=not everyday)
                if regex is not None:
                    self.literals.append(Pattern("term", row.cls, regex, row.where(), row.term, tokenised=fused))
            if row.kind == "re":
                if row.cls == "id-patterns" and row.term == ID_ROW:
                    self.id_row = row
                self.regexes.append(row)
            if row.kind == "phonetic":
                whitelist = self.firm_whitelist if row.cls == "firm" else \
                    [r.term for r in rows if r.kind == "whitelist" and r.parent is row]
                self.phonetic.append(PhoneticSource(row.cls, row.term, row.where(), whitelist))
        firm = settings["firm"]
        for term in [firm["name"]] + list(firm["renderings"]):
            where = "%s firm" % SETTINGS_NAME
            self.literals.append(Pattern("term", "firm", literal_regex(term, True, True), where, term, tokenised=True))
            self.phonetic.append(PhoneticSource("firm", term, where, self.firm_whitelist))
        for term, what in settings["seller_names"]:
            self.literals.append(Pattern("seller-account", "seller-account", literal_regex(term, True, True),
                                         "%s %s" % (SETTINGS_NAME, what), term, tokenised=True))
        self.seller_ids = settings["seller_ids"]
        for cls, group in (("internal-vocabulary", INTERNAL_VOCABULARY), ("sales-framing", SALES_FRAMING)):
            for term in group:
                self.literals.append(Pattern("term", cls, literal_regex(term), "the %s group" % cls, term))
        for term in INTERNAL_NOTE_PHRASES:
            self.literals.append(Pattern("internal-note", None, literal_regex(term), "the internal-notes group", term))
        self.plugin_words = plugin_words(rows)


def plugin_words(rows):
    """The words of the shipped plugin, assistant, method and markers rows: X26's plugin vocabulary."""
    found = set()
    for row in rows:
        if row.kind == "literal" and row.cls in ("plugin", "assistant", "method", "markers"):
            found.update(words_of(row.term))
    return found


def load_shipped(run):
    path = PLUGIN / "shared" / "leak-terms.txt"
    if not path.is_file():
        raise cannot(SHIPPED_NAME, WHOLE, "the shipped list is missing", "shared/leak-terms.txt of the plugin")
    rows = parse_list(run.text(path, SHIPPED_NAME), SHIPPED_NAME, local=False)
    if not any(row.kind == "re" and row.cls == "id-patterns" and row.term == ID_ROW for row in rows):
        raise cannot(SHIPPED_NAME, "class id-patterns", "the eight-digit monday id row is missing",
                     "the id-patterns row re: %s, which alone skips links (X34)" % ID_ROW)
    return rows


def load_local(run):
    path = run.home / "local" / "leak-terms.txt"
    if not path.exists():
        run.absent(LOCAL_NAME)
        return []
    if not path.is_file():
        raise cannot(LOCAL_NAME, WHOLE, "the local list is not a file", "a text file, or none")
    return parse_list(run.text(path, LOCAL_NAME), LOCAL_NAME, local=True)


def load_settings(run):
    """local/settings.json: schema settings/1 and a firm with a name, required; the seller's names and ids read."""
    path = run.home / "local" / "settings.json"
    if not path.is_file():
        raise cannot(SETTINGS_NAME, WHOLE, "there is no settings file, so the firm rule cannot run",
                     "local/settings.json under the home, as record.py home init writes it, with the firm block")
    data = json_value(run.text(path, SETTINGS_NAME), SETTINGS_NAME)
    if not isinstance(data, dict):
        raise cannot(SETTINGS_NAME, WHOLE, "the file is not a JSON object", "a settings/1 object")
    schema = data.get("schema")
    if schema != "settings/1":
        problem = "schema %s is newer than this plugin's or not this file's" % schema \
            if isinstance(schema, str) and mc.schema_newer(schema, "settings") else "schema %r is not settings/1" % schema
        raise cannot(SETTINGS_NAME, "schema", problem, "settings/1")
    firm = data.get("firm")
    if not isinstance(firm, dict) or not isinstance(firm.get("name"), str) or not words_of(firm.get("name") or ""):
        raise cannot(SETTINGS_NAME, "firm.name", "the firm has no name, so the firm rule cannot run",
                     "firm.name, the user's own firm name, which the first-run walkthrough writes")
    renderings = firm.get("renderings", [])
    if not isinstance(renderings, list) or not all(isinstance(r, str) and words_of(r) for r in renderings):
        raise cannot(SETTINGS_NAME, "firm.renderings", "the renderings are not a list of non-empty strings",
                     "firm.renderings, a list of strings (it may be empty)")
    names, ids = [], []

    def text_field(value, field):
        if value in (None, ""):
            return None
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise cannot(SETTINGS_NAME, field, "not a string", "a string")
        if not words_of(str(value)):  # F39: a blank or punctuation-only value would drop a rule without a word
            raise cannot(SETTINGS_NAME, field, "the value holds no letter or digit", "the value, or the field left "
                         "out")
        return str(value).strip()

    account = data.get("default_build_account")
    if account is not None:
        if not isinstance(account, dict):
            raise cannot(SETTINGS_NAME, "default_build_account", "not an object", "{slug, id}")
        slug, ident = text_field(account.get("slug"), "default_build_account.slug"), \
            text_field(account.get("id"), "default_build_account.id")
        if slug and words_of(slug):
            names.append((slug, "default_build_account.slug"))
        if ident:
            ids.append((ident, "default_build_account.id"))
    shown = data.get("never_show_workspaces", [])
    if shown is None:
        shown = []
    if not isinstance(shown, list):
        raise cannot(SETTINGS_NAME, "never_show_workspaces", "not a list", "a list of {id, name}")
    for index, item in enumerate(shown):
        field = "never_show_workspaces[%d]" % index
        if not isinstance(item, dict):
            raise cannot(SETTINGS_NAME, field, "not an object", "{id, name}")
        name, ident = text_field(item.get("name"), field + ".name"), text_field(item.get("id"), field + ".id")
        if name and words_of(name):
            names.append((name, field + ".name"))
        if ident:
            ids.append((ident, field + ".id"))
    github = text_field(data.get("github_account"), "github_account")
    if github and words_of(github):
        names.append((github, "github_account"))
    seller_ids = []
    for ident, field in ids:
        forms = {ident, ident.lstrip("0") or ident} if ident.isdigit() else {ident}
        for form in sorted(forms):
            seller_ids.append((re.compile(r"(?<!\d)%s(?!\d)" % re.escape(fold_text(form))), form, field))
    return {"firm": {"name": firm["name"], "renderings": renderings}, "seller_names": names, "seller_ids": seller_ids}


def load_lists(run):
    """The shipped list, the local list and the settings, read on every command that runs the firm rule."""
    if run.lists is None:
        rows = load_shipped(run) + load_local(run)
        run.lists = Lists(rows, load_settings(run))
    return run.lists


# Numbers (X25): digits with separators, currency and magnitude, number words, percentages; dates, times, versions,
# a year alone and list ordinals are not numbers. Values are exact fractions; precision is the unit of the last
# written digit.

UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
BIG = {"thousand": 1000, "grand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
NUMBER_WORDS = frozenset(set(UNITS) | set(TEENS) | set(TENS) | set(BIG) | {"hundred", "and", "a", "point", "half",
                                                                           "quarter", "of"})
NUMBER_START = frozenset(set(UNITS) | set(TEENS) | set(TENS) | {"a", "half"})
WORD_GAP = re.compile(r"[ \t]+|[ \t]*-[ \t]*|[ \t]*-?[ \t]*\n[ \t]*")
_CURRENCY = r"[$£€¥]|(?:" + "|".join(CURRENCY_CODES) + r")(?![^\W\d_])"  # a code may sit on the digits (F01)
# A number may follow a sign, a dash, a slash, a quote or an abbreviation's full stop (F01); it never starts inside a
# digit run (after a digit and a separator) or after a full stop that does not follow a letter (a decimal tail).
NUMBER = re.compile(r"(?<!\w)(?<!\d[.,'\u202f])(?:(?<!\.)|(?<=[^\W\d_]\.))(?P<pre>(?:" + _CURRENCY + r")[ \t]?)?"
                    r"(?P<int>\d{1,3}(?:[,' ]\d{3})+(?!\d)|\d+)(?P<dec>\.\d+)?(?P<exp>e[+-]?\d{1,2}(?!\d))?"
                    r"(?P<mag>(?:[ \t-]?(?:thousand|million|billion|grand)|[ \t]?(?:bn|mm|k|m))(?![^\W\d_]))?"
                    r"(?P<pct>[ \t]?(?:%|percent\b|per[ \t]+cent\b))?"
                    r"(?P<post>[ \t]?(?:" + _CURRENCY + r"))?(?![^\W_])")
MAGNITUDE = {"k": 1000, "thousand": 1000, "grand": 1000, "m": 10 ** 6, "mm": 10 ** 6, "million": 10 ** 6,
             "bn": 10 ** 9, "billion": 10 ** 9}
PERCENT_AFTER = re.compile(r"[ \t]?(?:%|percent\b|per[ \t]+cent\b)")
RATE_AFTER = re.compile(RATE_SUFFIX)
_MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|"
          r"apr|jun|jul|aug|sept|sep|oct|nov|dec)")
MONTHS = {name: number for number, names in enumerate(
    (("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",), ("june", "jun"),
     ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
     ("december", "dec")), 1) for name in names}
DATE_YMD = re.compile(r"(?<![\d.])(\d{4})(?:-|/|\.)(\d{1,2})(?:-|/|\.)(\d{1,2})(?![\d])")
DATE_DMY = re.compile(r"(?<![\d.])(\d{1,2})(?:-|/|\.)(\d{1,2})(?:-|/|\.)(\d{4})(?![\d])")
DATE_DAY_MONTH = re.compile(r"(?<![\d.])(\d{1,2})(?:st|nd|rd|th)?[ \t]+(?:of[ \t]+)?(" + _MONTH + r")\b\.?"
                            r"(?:,?[ \t]+(\d{4}))?(?!\d)")
DATE_MONTH_DAY = re.compile(r"\b(" + _MONTH + r")\b\.?[ \t]+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?[ \t]+(\d{4}))?(?!\d)")
DATE_MONTH_YEAR = re.compile(r"\b(" + _MONTH + r")\b\.?[ \t]+(\d{4})(?!\d)")
TIMES = (re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:])(?:[ \t]?[ap]\.?m\b\.?)?"),
         re.compile(r"(?<![\d.])\d{1,2}[ \t]?[ap]\.?m\b\.?"))
VERSIONS = (re.compile(r"\bv\d+(?:\.\d+)+\b"), re.compile(r"(?<![\d.])\d+\.\d+\.\d+(?:\.\d+)*(?![\d.])"))
YEAR = re.compile(r"(?<![\d$£€¥.,' ])(?<![$£€¥] )(?:19|20)\d{2}(?![\d%])(?![ \t]?(?:k|mm|m|bn|thousand|million|"
                  r"billion|grand|percent)(?![^\W\d_]))")
ORDINAL = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|[-*+>][ \t]+)?(\d{1,3})[.)](?=[ \t]|$)")
DIGIT_RUN = re.compile(r"\d+")
CHAIN_JOIN = re.compile(r"[ \t]|[ \t]*\n[ \t]*|[ \t]*\|[ \t]*|[ \t]?[*_~`]+[ \t]?")
CHAIN_THREE = re.compile(r"[.\-/_]")
CHAIN_COMMA = re.compile(r"[,'\u2019][ \t]*\n[ \t]*|[,'\u2019][ \t]+")  # F22: a thousands mark, then a break or a space
ID_JOIN = re.compile(r"[ .\-]")
TABLE_RULE = re.compile(r"[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*|[ \t]*\|[ \t]*:?-+:?[ \t]*\|[ \t]*")
ID_SHAPE = re.compile(r"\d{8,}")  # a bare run of eight digits or more: the id row's shape, never lent a table's cue
COST_RE = re.compile(r"[$£€¥]|(?<!%s)(?:%s)(?!%s)" % (WORDCHAR, "|".join(
    "[\\s-]+".join(re.escape(w) for w in cue.split()) for cue in sorted(COST_CUES + CURRENCY_CODES, key=len,
                                                                         reverse=True)), WORDCHAR))


def valid_date(year, month, day):
    try:
        date(int(year), int(month), int(day))
    except ValueError:
        return False
    return 1900 <= int(year) <= 2099


def date_spans(text):
    """Spans of well-formed dates and times, and of versions: never figures and never warned (X25)."""
    spans = []
    for match in DATE_YMD.finditer(text):
        if valid_date(match.group(1), match.group(2), match.group(3)):
            spans.append(match.span())
    for match in DATE_DMY.finditer(text):
        a, b, year = match.groups()
        if valid_date(year, b, a) or valid_date(year, a, b):
            spans.append(match.span())
    for pattern, order in ((DATE_DAY_MONTH, "dm"), (DATE_MONTH_DAY, "md")):
        for match in pattern.finditer(text):
            day, month = (match.group(1), match.group(2)) if order == "dm" else (match.group(2), match.group(1))
            if valid_date(match.group(3) or 2000, MONTHS[month], day):
                spans.append(match.span())
    spans += [m.span() for m in DATE_MONTH_YEAR.finditer(text)]
    for pattern in TIMES + VERSIONS:
        spans += [m.span() for m in pattern.finditer(text)]
    return spans


def number_masks(text):
    """Date, time and version spans, then a year written alone and the ordinals of a list."""
    spans = date_spans(text)
    spans += [m.span() for m in YEAR.finditer(text)]
    spans += [m.span(1) for m in ORDINAL.finditer(text)]
    return sorted(spans)


def overlaps(spans, start, end):
    return any(s < end and start < e for s, e in spans)


def precision_of(value):
    """The unit of the last written digit of a value spelled in words: 45,000 has 1,000; 1.2 has 0.1."""
    if value == 0:
        return Fraction(1)
    if value.denominator != 1:
        k = 0
        while (value * 10 ** k).denominator != 1 and k < 12:
            k += 1
        return Fraction(1, 10 ** k)
    unit, number = 1, int(value)
    while number % 10 == 0:
        number //= 10
        unit *= 10
    return Fraction(unit)


def words_number(words):
    """(value, count) of the longest number the words begin with, or (None, 0)."""
    if len(words) >= 3 and words[0] == "half" and words[1] == "a" and words[2] in BIG and words[2] != "grand":
        return Fraction(BIG[words[2]], 2), 3
    if len(words) >= 5 and words[:4] == ["a", "quarter", "of", "a"] and words[4] in BIG and words[4] != "grand":
        return Fraction(BIG[words[4]], 4), 5
    total, group, state, big_last, best, i = Fraction(0), Fraction(0), None, None, (None, 0), 0
    while i < len(words):
        word = words[i]
        if word == "a":
            if state is not None or i + 1 >= len(words) or words[i + 1] not in ("hundred", "thousand", "million",
                                                                                "billion"):
                break
            group, state, i = Fraction(1), "unit", i + 1
            continue
        if word in UNITS or word in TEENS:
            value = UNITS.get(word, TEENS.get(word))
            if not (state == "ten" and word in UNITS and value) and state not in (None, "hundred", "and", "big"):
                break
            group, state = group + value, ("teen" if word in TEENS else "unit")
        elif word in TENS:
            if state not in (None, "hundred", "and", "big"):
                break
            group, state = group + TENS[word], "ten"
        elif word == "hundred":
            if state not in ("unit", "teen", "ten") or group >= 100:
                break
            group, state = group * 100, "hundred"
        elif word in BIG:
            scale = BIG[word]
            if state in (None, "and") or (big_last is not None and scale >= big_last):
                break
            total, group, big_last, state = total + group * scale, Fraction(0), scale, "big"
        elif word == "and":
            # A33 (R67): "four and a half thousand" is 4,500, as "four point five thousand" is
            if state in ("unit", "teen", "ten") and words[i + 1:i + 3] == ["a", "half"] and i + 3 < len(words) and \
                    words[i + 3] in BIG and (big_last is None or BIG[words[i + 3]] < big_last):
                scale = BIG[words[i + 3]]
                total, group, big_last, state = total + (group + Fraction(1, 2)) * scale, Fraction(0), scale, "big"
                i += 4
                best = (total, i)
                continue
            if state not in ("hundred", "big"):
                break
            state, i = "and", i + 1
            continue
        elif word == "point":
            if state not in ("unit", "teen", "ten"):
                break
            j, digits = i + 1, ""
            while j < len(words) and words[j] in UNITS:
                digits, j = digits + str(UNITS[words[j]]), j + 1
            if not digits:
                break
            group, state, i = group + Fraction(int(digits), 10 ** len(digits)), "point", j
            best = (total + group, i)
            continue
        else:
            break
        i += 1
        best = (total + group, i)
    return best


class Number:
    """One number read from a text: its value and precision, where it is, and what is written beside it."""
    __slots__ = ("value", "precision", "percent", "currency", "rate", "start", "end", "split", "cue", "digits",
                 "plain")

    def __init__(self, value, precision, start, end, percent=False, currency=False, rate=False, split=False,
                 digits=False, plain=False):
        self.value, self.precision, self.start, self.end = value, precision, start, end
        self.percent, self.currency, self.rate, self.split = percent, currency, rate, split
        self.cue, self.digits, self.plain = False, digits, plain

    def matches(self, value, precision):
        return abs(self.value - value) < max(self.precision, precision)


def parse_numbers(folded, original, masks=None):
    """Every number of a folded text: digits (with both readings of a lower-case m) and number words; each knows
    whether its sentence holds a cost cue (X25)."""
    text = folded.text
    masks = number_masks(text) if masks is None else masks
    found = []
    for match in NUMBER.finditer(text):
        if overlaps(masks, match.start("int"), match.end("int")):
            continue
        integer = re.sub(r"[,' ]", "", match.group("int"))
        decimals = (match.group("dec") or "")[1:]
        value = Fraction(int(integer + decimals), 10 ** len(decimals))
        precision = Fraction(1, 10 ** len(decimals))
        if match.group("exp"):  # G23 (R58): an exponent (4.1287e5) scales the value and its last written digit
            scale = Fraction(10) ** int(match.group("exp")[1:])
            value, precision = value * scale, precision * scale
        currency = bool(match.group("pre") or match.group("post"))
        percent = bool(match.group("pct"))
        rate = bool(RATE_AFTER.match(text, match.end()))
        written = match.group("mag") or ""
        magnitude = written.strip(" \t-")
        readings = [1]
        if magnitude:
            scale = MAGNITUDE[magnitude]
            word = match.start("mag") + len(written) - len(magnitude)
            start, _ = folded.span(word, match.end("mag"))
            lower = magnitude in ("m", "mm") and original[start:start + 1].islower() and not currency
            readings = [scale, 1] if lower else [scale]
        for scale in readings:
            found.append(Number(value * scale, precision * scale, match.start(), match.end(), percent, currency,
                                rate, digits=True, plain=not magnitude and not decimals and not currency and
                                not match.group("exp")))
    words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[a-z]+", text)]
    i = 0
    while i < len(words):
        if words[i][0] not in NUMBER_START:
            i += 1
            continue
        run, j = [words[i]], i
        while j + 1 < len(words) and words[j + 1][0] in NUMBER_WORDS and \
                WORD_GAP.fullmatch(text[words[j][2]:words[j + 1][1]]):
            run.append(words[j + 1])
            j += 1
        value, count = words_number([w for w, _, _ in run])
        if value is None or count == 0:
            i += 1
            continue
        used = run[:count]
        start, end = used[0][1], used[-1][2]
        split = any("\n" in text[used[k][2]:used[k + 1][1]] for k in range(len(used) - 1))
        after = PERCENT_AFTER.match(text, end)
        number = Number(value, precision_of(value), start, after.end() if after else end, percent=bool(after),
                        rate=bool(RATE_AFTER.match(text, end)), split=split)
        found.append(number)
        i += count
    sentences = sentence_spans(text)
    starts = [s for s, _ in sentences]
    cues = [bool(COST_RE.search(text, s, e)) for s, e in sentences]
    rows = table_cues(text) if "|" in text else []
    row_starts = [s for s, _, _ in rows]
    for number in found:
        index = max(0, bisect.bisect_right(starts, number.start) - 1)
        number.cue = (cues[index] if cues else False) or number.currency  # a code on the digits is a cue too
        if not number.cue and rows:  # G21 (R56): a table row's sentence also reads its header and first cell
            row = rows[max(0, bisect.bisect_right(row_starts, number.start) - 1)]
            number.cue = row[0] <= number.start < row[1] and row[2] and not (
                number.plain and ID_SHAPE.fullmatch(text, number.start, number.end))
    return found


def table_cues(text):
    """G21 (R56): (start, end, cue) of each body row of a Markdown table, where cue says whether the table's header
    row or the row's first cell holds a cost cue (X25). A table is a line holding a pipe followed by a rule row
    (`|---|---|`, outer pipes optional), and the lines holding a pipe after it; a run of lines that each start
    with a pipe and have no rule row is read as a table whose first line is the header, the fail-safe side."""
    lines, position = [], 0
    for line in text.split("\n"):
        lines.append((position, position + len(line), line))
        position += len(line) + 1
    rows, i = [], 0
    while i < len(lines):
        line = lines[i][2]
        ruled = "|" in line and i + 1 < len(lines) and TABLE_RULE.fullmatch(lines[i + 1][2])
        if not ruled and not line.lstrip().startswith("|"):
            i += 1
            continue
        header = bool(COST_RE.search(line))
        j = i + 2 if ruled else i + 1
        while j < len(lines) and "|" in lines[j][2] and (ruled or lines[j][2].lstrip().startswith("|")):
            start, end, body = lines[j]
            cells = body.strip()
            cells = cells[1:] if cells.startswith("|") else cells
            first = cells.split("|", 1)[0]
            rows.append((start, end, header or bool(COST_RE.search(first))))
            j += 1
        i = max(j, i + 1)
    return rows


def digit_chains(text, masks):
    """Digit groups joined by single spaces, a line break, a table pipe or emphasis marks, or by a dot, hyphen,
    slash or underscore before a group of three: a figure in split rendering, read as one number (X25)."""
    chains, current = [], []

    def close():
        if len(current) >= 2:
            chains.append(list(current))
        del current[:]

    for match in DIGIT_RUN.finditer(text):
        s, e = match.span()
        if (s and text[s - 1].isalpha()) or (e < len(text) and text[e].isalpha()) or overlaps(masks, s, e):
            close()
            continue
        if current:
            separator = text[current[-1][1]:s]
            if CHAIN_JOIN.fullmatch(separator) or (e - s == 3 and (CHAIN_THREE.fullmatch(separator) or
                                                                   CHAIN_COMMA.fullmatch(separator))):
                current.append((s, e))
                continue
            close()
        current.append((s, e))
    close()
    return chains


def chain_is_date(text, groups):
    """Y02: three groups of 1-2, 1-2 and 4 digits (or 4, 2 and 2) that form a real date are a date."""
    if len(groups) != 3:
        return False
    parts = [text[s:e] for s, e in groups]
    sizes = [len(p) for p in parts]
    if sizes[2] == 4 and sizes[0] <= 2 and sizes[1] <= 2:
        return valid_date(parts[2], parts[1], parts[0]) or valid_date(parts[2], parts[0], parts[1])
    if sizes[0] == 4 and sizes[1] <= 2 and sizes[2] <= 2:
        return valid_date(parts[0], parts[1], parts[2])
    return False


def id_chains(text):
    """X34: digit groups of two to four joined by single spaces, hyphens or dots, eight digits or more in all."""
    chains, current = [], []

    def close():
        if len(current) >= 2 and sum(e - s for s, e in current) >= 8:
            chains.append(list(current))
        del current[:]

    for match in DIGIT_RUN.finditer(text):
        s, e = match.span()
        good = 2 <= e - s <= 4 and not (s and (text[s - 1].isalnum() or text[s - 1] in "/:")) and \
            not (e < len(text) and (text[e].isalnum() or text[e] == ":"))
        if not good:
            close()
            continue
        if current and not ID_JOIN.fullmatch(text[current[-1][1]:s]):
            close()
        current.append((s, e))
    close()
    return chains


def whole_number(term):
    """The one number a term reads as, when the whole term is that number (an exclusion's figure row), else None."""
    folded = fold(term.strip())
    found = [n for n in parse_numbers(folded, term.strip(), masks=[]) if n.start == 0 and n.end == len(folded.text)]
    return found[0] if found else None


# The record's own sets (X11, Y01): F the figures, R the internal runs, Q the client quotes and E the client's
# document text, the exemption source of the copied-run rule. Read fresh on every run; nothing is cached.

class Segment:
    __slots__ = ("file", "part", "text", "flags")

    def __init__(self, file, part, text, flags):
        self.file, self.part, self.text, self.flags = file, part, text, flags


def blank_marks(text):
    """Y03: a line that is exactly one of the four marks is never checked text; its characters become spaces."""
    if "<!--" not in text:
        return text
    lines = text.split("\n")
    return "\n".join(" " * len(line) if line.strip() in BLOCK_MARKS else line for line in lines)


def block_lines(lines, start_mark, end_mark):
    """(set of line indexes inside well-formed blocks, problem or None): X09's marks, several blocks allowed; a
    mark out of order exempts nothing and gives the 1-based line and the problem."""
    inside_lines, open_at = set(), None
    kind = start_mark.split()[1].split(":")[0]
    for index, line in enumerate(lines):
        mark = line.strip()
        if mark not in (start_mark, end_mark) and "<!" in mark and near_mark(mark) == kind:
            return set(), (index + 1, "a mark not written in the pinned form")  # F20
        if mark == start_mark:
            if open_at is not None:
                return set(), (index + 1, "a second opening mark inside an open block")
            open_at = index
        elif mark == end_mark:
            if open_at is None:
                return set(), (index + 1, "a closing mark with no opening mark")
            inside_lines.update(range(open_at + 1, index))
            open_at = None
    if open_at is not None:
        return set(), (open_at + 1, "an opening mark with no closing mark")
    return inside_lines, None


NEAR_MARK = re.compile(r"^<!-*\s*(client.?safe|glossary)\s*\W?\s*(?:start|end)\s*-*>$")


def near_mark(line):
    """F20 (X09): "client-safe" or "glossary" when a line reads like one of the four marks, letter case, spacing and a
    dash look-alike aside, else None."""
    match = NEAR_MARK.match(fold_text(line.strip()))
    if not match:
        return None
    return "glossary" if match.group(1) == "glossary" else "client-safe"


def section_lines(lines, title):
    """Indexes of the lines under a level-2 heading `title` (letter case ignored), up to the next level 1 or 2."""
    found, active = set(), False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            active = len(heading.group(1)) == 2 and line.strip().lower() == title.lower()
            continue
        if active:
            found.add(index)
    return found


def blueprint_client_lines(lines):
    """The blueprint's client-facing lines (X09): sections 1 to 15, the prompt blocks, the glossary blocks."""
    found, active = set(), False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            active = section_number(line) in CLIENT_SECTIONS
            continue
        if active:
            found.add(index)
    for index, line in enumerate(lines):
        if re.match(r"^###\s+Prompt\s+\S", line):
            j = index + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                if HEADING.match(lines[j]):
                    break
                j += 1
            if j < len(lines) and lines[j].strip().startswith("```"):
                k = j + 1
                while k < len(lines) and not lines[k].strip().startswith("```"):
                    found.add(k)
                    k += 1
    glossary, _ = block_lines(lines, BLOCK_MARKS[2], BLOCK_MARKS[3])
    return found | glossary


def front_matter_lines(text):
    """The lines of a front matter block that opens the text (an unclosed one runs to the end), or None."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index]
    return lines[1:]


def input_kind(rel, text):
    """What an inputs/*.md file is (X11, F03): "snapshot" when its front matter names document-summary/1, quoted or
    not; "internal" when it has front matter with no schema line, which the lint cannot place and so never takes as
    client-document text; "raw" with no front matter. A newer or another schema is exit 3 (G57, A9.6)."""
    block = front_matter_lines(text)
    if block is None:
        return "raw"
    schemas = [m.group(1) for m in (SCHEMA_LINE.match(line) for line in block) if m]
    if not schemas:
        return "internal"
    found = SNAPSHOT_SCHEMA.fullmatch(schemas[0])
    if found and int(found.group(1)) == 1 and len(set(schemas)) == 1:
        return "snapshot"
    if found and int(found.group(1)) > 1:
        raise cannot(rel, "schema", "schema %s is newer than this lint's" % schemas[0], "document-summary/1")
    raise cannot(rel, "schema", "schema %r is not a document snapshot's" % schemas[0], "document-summary/1, or a raw "
                 "client document with no front matter")


def is_snapshot(rel, text):
    return rel.lower().endswith(".md") and input_kind(rel, text) == "snapshot"


def quote_texts(line, whole=False):
    """X24: the client quote a marked line holds: the text between double quotation marks, else the line with the
    marker, the location forms and the speaker label removed. With `whole` (the Q set, F06), a line that holds
    quotation marks gives both: a word quoted inside an utterance never shrinks the quote to that word."""
    quoted = [m.group(1) for m in QUOTE_SPANS.finditer(line)]
    if quoted and not whole:
        return quoted
    rest = line
    for marker in MARKERS[:5]:
        rest = re.sub(re.escape(marker), " ", rest, flags=re.IGNORECASE)
    rest = LOCATION.sub(" ", rest)
    if ":" in rest:
        rest = rest.split(":", 1)[1]
    return quoted + [rest]


QUOTE_MARK = re.compile("|".join(re.escape(m) for m in MARKERS[:5]), re.IGNORECASE)
DOC_MARK = re.compile(re.escape(MARKERS[4]), re.IGNORECASE)


def kind_of(rel):
    """What a record file feeds, by its record-relative path (X11, Y01)."""
    parts = rel.split("/")
    name = parts[-1]
    if parts[0] == "inputs":
        return "input"
    if parts[0] == "calls":
        return "call" if name.lower().endswith(".md") else "transcript"
    if parts[-2:] == ["live", "live-map.md"]:
        return "skip"
    if len(parts) >= 3 and parts[0] == "strands":
        tail = parts[2:]
        if tail == ["solution", "exclusions.md"] or tail == ["solution", "allowlist.md"]:
            return "skip"
        if tail == ["solution", "blueprint.md"] or (len(tail) == 3 and tail[0] == "versions" and
                                                   re.fullmatch(r"blueprint-r\d+\.md", tail[2])):
            return "blueprint"
    if rel in ("CLIENT.md", "meetings.md", "log.md"):
        return "plain"
    return "internal"


def skipped_dir(parts):
    """Folders that feed no set: .work/, every strand's drafts/ and deliverables/, and .git/."""
    if parts[-1] in (".work", ".git", "__pycache__"):
        return True
    return len(parts) == 3 and parts[0] == "strands" and parts[2] in ("drafts", "deliverables")


def real_parts(real, base):
    """The parts of a resolved path relative to the resolved base, or None when it lies outside."""
    try:
        return Path(real).relative_to(base).parts
    except ValueError:
        return None


def walk_inside(top, base, failed, outside, skip=None):
    """R09, R38: (walked folder, real parts, file names) for each folder under top. A linked folder is followed once
    when it resolves inside base, and outside(path, True) raises (exit 3) when it resolves outside. The parts are
    the folder's real place relative to base, so a link never changes a file's name or kind; skip(parts) leaves a
    folder out by that real place."""
    base = os.path.realpath(str(base))
    seen = {os.path.realpath(str(top))}
    for folder, dirs, files in os.walk(str(top), onerror=failed, followlinks=True):
        kept = []
        for name in sorted(dirs):
            real = os.path.realpath(os.path.join(folder, name))
            parts = real_parts(real, base)
            if parts is None:
                outside(os.path.join(folder, name), True)
            if real in seen or (skip and skip(parts)):
                continue
            seen.add(real)
            kept.append(name)
        dirs[:] = kept
        yield folder, real_parts(os.path.realpath(folder), base), sorted(files)


def walk_files(top, base, failed, outside, skip=None):
    """{real POSIX name relative to base: path} of every file walk_inside finds, system files left out. A linked
    file is read under its real name, once, and outside(path, False) raises when it resolves outside base (R38)."""
    found, real_base = {}, os.path.realpath(str(base))
    for folder, _, files in walk_inside(top, base, failed, outside, skip):
        for name in files:
            if name.lower() in SYSTEM_FILES:
                continue
            path = os.path.join(folder, name)
            parts = real_parts(os.path.realpath(path), real_base)
            if parts is None:
                outside(path, False)
            if skip and skip(parts[:-1]):
                continue
            found.setdefault("/".join(parts), Path(path))
    return found


def record_walk(root, failed, outside):
    """{record-relative name: path} of every .md, .txt and .docx under a record folder that may feed a set (X11):
    .work/, drafts/, deliverables/ and .git/ left out, a link followed inside the record and named by its real
    place, and outside(path, folder) called for one that resolves outside (R38). record_files and the age check
    of R44 both walk this way, so the files an entry is built from and the files its age is taken from never drift."""

    def skip(parts):
        return any(skipped_dir(parts[:end]) for end in range(1, len(parts) + 1))

    found = walk_files(root, root, failed, outside, skip)
    return {rel: path for rel, path in found.items() if os.path.splitext(rel)[1].lower() in TEXT_EXT}


def record_failures(run):
    """(failed, outside) for a walk of this record: each names a path in this record, never a link's target."""

    def failed(exc):
        raise cannot(run.name(exc.filename or run.root), WHOLE, "cannot list the folder: %s" % exc,
                     "a readable record folder")

    def outside(path, folder):  # X30: the link in this record is named, never what it points at
        raise cannot(run.name(path), WHOLE, "a linked %s resolves outside the record" % ("folder" if folder else
                     "file"), "files inside the record only; copy them in or remove the link, then run this again")

    return failed, outside


def record_files(run):
    """Every .md, .txt and .docx of the record that may feed a set, in sorted POSIX path order. A link is
    followed inside the record and named by its real place; one that resolves outside is exit 3 (R38)."""
    return sorted(record_walk(run.root, *record_failures(run)))


def lines_to_segments(file, lines, tags):
    """Contiguous lines with the same tag become one segment; a None tag is left out."""
    segments, current, tag = [], [], None
    for line, this in zip(lines, tags):
        if this != tag and current:
            if tag is not None:
                segments.append(Segment(file, tag[0], "\n".join(current), tag[1]))
            current = []
        tag = this
        current.append(line)
    if current and tag is not None:
        segments.append(Segment(file, tag[0], "\n".join(current), tag[1]))
    return segments


def file_segments(run, rel, text):
    """The segments one record file gives, each tagged with the sets it feeds and with body or block."""
    kind = kind_of(rel)
    if kind == "skip":
        return []
    lines = text.split("\n")
    marks = [line.strip() in BLOCK_MARKS for line in lines]
    body_all, body_noq = ("body", frozenset("FRQ")), ("body", frozenset("FR"))
    if kind in ("plain", "transcript"):
        return lines_to_segments(rel, lines, [None if m else body_noq for m in marks])
    if kind == "internal":
        return lines_to_segments(rel, lines, [None if m else body_all for m in marks])
    state = input_kind(rel, text) if kind == "input" and rel.lower().endswith(".md") else "raw"
    if kind == "input" and state == "internal":
        return lines_to_segments(rel, lines, [None if m else body_all for m in marks])
    if kind == "input" and state == "raw":
        return lines_to_segments(rel, lines, [None if m else ("body", frozenset("FE")) for m in marks])
    if kind == "blueprint":  # R52: a heading of sections 1 to 15 is client-facing, so it feeds no set either
        client = blueprint_client_lines(lines) | {i for i, line in enumerate(lines) if section_number(line) in
                                                  CLIENT_SECTIONS}
        return lines_to_segments(rel, lines, [None if m or i in client else body_all for i, m in enumerate(marks)])
    blocks, problem = block_lines(lines, BLOCK_MARKS[0], BLOCK_MARKS[1])
    if problem:
        run.add(record_warning(rel, problem[0], "client-safe marks not well formed (%s); nothing in this file is "
                               "exempt" % problem[1], "an opening and a closing mark, each alone on its line"))
    conflicts = section_lines(lines, HEADINGS[0])
    tags = []
    for index, mark in enumerate(marks):
        if mark:
            tags.append(None)
        elif index in conflicts:
            tags.append(("body", frozenset("FRQC")))
        elif index in blocks:
            tags.append(("block", frozenset("FQ")))
        else:
            tags.append(body_all)
    segments = lines_to_segments(rel, lines, tags)
    if kind == "input":
        for line in lines:
            if DOC_MARK.search(line):
                for quote in quote_texts(line):
                    segments.append(Segment(rel, "body", quote, frozenset("E")))
    return segments


def record_warning(file, line, problem, expected, rule="copied-run"):
    return {"file": file, "field": "line %d" % line, "problem": problem, "expected": expected, "rule": rule,
            "class": None, "severity": "warn", "line": line, "column": 1, "match": None, "source": None,
            "_order": (9, file, line, 0, 0)}


def docx_text(run, path, name):
    """(text of every part joined, parts read, the parts as (part, paragraphs, labels)) of a .docx (X35)."""
    data = run.read(path, name, limit=DOCX_TOTAL_LIMIT)
    parts = docx_parts(data, name)
    run.inputs[name]["parts_read"] = [part for part, _, _ in parts]
    return parts


class Sets:
    """F, R, Q and E with the file and part each entry came from, so a checked file never feeds its own check."""

    def __init__(self):
        self.cost, self.cost_percent, self.record, self.record_percent = [], [], [], []
        self.runs, self.docs, self.quotes = {}, {}, {}
        self.run_tokens, self.doc_tokens, self.quote_tokens = [], [], []
        self.indexes = {}

    def add_numbers(self, segment):
        folded = fold(segment.text)
        for number in parse_numbers(folded, segment.text):
            # A33 (R67): a number below 100 is no client figure. A word number takes the unit of its last written
            # digit as its precision, so "ten" beside a cost word was the figure 10 give or take 10, and it met
            # "one", "Satellite 1" and "two-way" in demo 1.
            if number.split or number.value < SMALL_FIGURE and not number.percent:
                continue
            if number.percent and number.value < 10:
                continue
            entry = (number.value, number.precision, segment.file, segment.part)
            if number.cue:
                (self.cost_percent if number.percent else self.cost).append(entry)
            else:
                (self.record_percent if number.percent else self.record).append(entry)

    def add_grams(self, index, words, size, entry):
        for i in range(len(words) - size + 1):
            index.setdefault(tuple(words[i:i + size]), []).append(entry)

    def index(self, which, kind):
        """F14, F15: the substitution ("sub") or deletion ("del") index of R, E or Q, built once on first use."""
        key = (which, kind)
        if key not in self.indexes:
            sources = {"runs": self.run_tokens, "docs": self.doc_tokens, "quotes": self.quote_tokens}[which]
            inner = which == "quotes"  # F15: a quote's first and last words stay, so seven words never block
            self.indexes[key] = near_index(sources, inner) if kind == "sub" else deletion_index(sources, inner)
        return self.indexes[key]


def deletion_index(sources, inner=False):
    """F14: every eight-word window of a source with each word in turn left out, as seven-word tuples. A checked
    seven-word window found here dropped a word; a checked eight-word window with one word left out found here
    added one (or changed one)."""
    index = {}
    for words, entry in sources:
        for i in range(len(words) - NEAR_WORDS + 1):
            window = words[i:i + NEAR_WORDS]
            for position in positions(inner):
                index.setdefault(tuple(window[:position]) + tuple(window[position + 1:]), []).append(entry)
    return index


def positions(inner):
    """The positions of an eight-word window a near copy may change: all, or (for a quote) all but the two ends."""
    return range(1, NEAR_WORDS - 1) if inner else range(NEAR_WORDS)


def near_index(sources, inner=False):
    index = {}
    for words, entry in sources:
        for i in range(len(words) - NEAR_WORDS + 1):
            window = words[i:i + NEAR_WORDS]
            for position in positions(inner):
                key = (position,) + tuple(window[:position]) + tuple(window[position + 1:])
                index.setdefault(key, []).append(entry)
    return index


ELEMENT_KEYS = "## Element keys"  # the blueprint's element-key table, after section 16: | key | kind | name | notifies |


class Plan:
    """A36 (R73): the planned values of a strand's frozen revision as word runs: each run of six, seven and eight
    words, and the near-copy indexes of F14, so a checked window one word away from a planned value is found too."""

    def __init__(self, streams):
        self.grams = {tuple(words[i:i + size]) for words in streams for size in (RUN_WORDS, NEAR_WORDS - 1, NEAR_WORDS)
                      for i in range(len(words) - size + 1)}
        sources = [(words, None) for words in streams]
        self.sub, self.dele = near_index(sources), deletion_index(sources)

    def holds(self, gram, lookups=()):
        return gram in self.grams or any(key in (self.sub if kind == "sub" else self.dele) for kind, key in lookups)


def planned_streams(lines):
    """A36 (R73): the word runs of a frozen revision's planned values: its client-facing lines (sections 1 to 15, the
    prompt blocks and the glossary, X09), section 16's sample data plan (a subsection whose title holds the word
    "sample", or a line that opens with it, A28), and each name cell of the element-key table. The rest of section
    16 (the assumption ids, assumed terms, forks and build checks) and the table's key and kind cells are no planned
    value, so a run copied from them still counts."""
    chosen, internal, sample = set(blueprint_client_lines(lines)), False, None
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            internal, sample = section_number(line) == 16, None
            continue
        if not internal:
            continue
        if heading:
            level = len(heading.group(1))
            if sample is not None and level <= sample:
                sample = None
            if sample is None and "sample" in words_of(heading.group(2)):
                sample = level
            continue
        if sample is not None or words_of(line)[:1] == ["sample"]:
            chosen.add(index)
    streams, current = [], []
    for index, line in enumerate(lines + [""]):
        if index in chosen:
            current.append(line)
        elif current:
            streams.append(words_of("\n".join(current)))
            current = []
    for index in sorted(section_lines(lines, ELEMENT_KEYS)):
        line = lines[index].strip()
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and cells[0].lower() != "key" and not TABLE_RULE.fullmatch(line):
            streams.append(words_of(cells[2]))
    return [words for words in streams if words]


def frozen_plan(run, strand):
    """A36 (R73): the Plan of the strand's frozen revision, the one its build writes from: STRAND.md's version, that
    version's version.md revision, and versions/<version>/blueprint-r<revision>.md, all read from the record's
    texts; None when any of them is missing or cannot be read, so every run still counts (fail-safe)."""
    if strand not in run.plans:
        run.plans[strand], texts = None, record_texts(run)
        found = [p for p in strand_folders(run) if p.name.startswith("%s-" % strand)]
        base = "strands/%s" % found[0].name if found else None
        try:
            version = mc.front_matter(texts.get("%s/STRAND.md" % base) or "", "STRAND.md").get("version") or ""
            revision = mc.front_matter(texts.get("%s/versions/%s/version.md" % (base, version)) or "",
                                       "version.md").get("revision") or ""
        except mc.FrontMatterError:
            version = revision = ""
        text = texts.get("%s/versions/%s/blueprint-r%s.md" % (base, version, revision)) \
            if base and re.fullmatch(r"v\d+(?:\.\d+)*", version) and revision.isdigit() else None
        if text is not None:
            run.plans[strand] = Plan(planned_streams(text.split("\n")))
    return run.plans[strand]


def record_texts(run):
    """{record-relative name: text} of every file record_files lists, read once per run and kept for the wall's
    own set O and the index's harvest (X11, X26, X27)."""
    if run.texts is None:
        texts = {}
        for rel in record_files(run):
            path = run.root.joinpath(*rel.split("/"))
            if rel.lower().endswith(".docx"):
                texts[rel] = "\n".join("\n".join(paragraphs) for _, paragraphs, _ in docx_text(run, path, rel))
            else:
                texts[rel] = run.text(path, rel)
        run.texts = texts
    return run.texts


def build_sets(run):
    """Read every record file the sets need (X11), listing each with its hash, and build F, R, Q and E."""
    sets = Sets()
    for rel, text in record_texts(run).items():
        for segment in file_segments(run, rel, text):
            flags = segment.flags
            if "F" in flags:
                sets.add_numbers(segment)
            words = words_of(segment.text)
            if "R" in flags:
                entry = (segment.file, segment.part, "C" in flags)
                sets.add_grams(sets.runs, words, RUN_WORDS, entry)
                sets.run_tokens.append((words, entry))
            if "E" in flags:
                entry = (segment.file, segment.part, False)
                sets.add_grams(sets.docs, words, RUN_WORDS, entry)
                sets.doc_tokens.append((words, entry))
            if "Q" in flags:
                for line in segment.text.split("\n"):
                    if QUOTE_MARK.search(line):
                        for quote in quote_texts(line, whole=True):
                            quote_words = words_of(quote)
                            sets.add_grams(sets.quotes, quote_words, QUOTE_WORDS, (segment.file, segment.part))
                            sets.quote_tokens.append((quote_words, (segment.file, segment.part)))
    return sets


# The strand's exclusions (every strand) and allowlist (its own strand only), X09, X10, Y05.

ROW_LINE = re.compile(r"^-\s+(.*)$")
KEY_GROUP = re.compile(r"^(.*?)\s*\[([^\[\]]*)\]\s*$")
PAIR = re.compile(r"^\s*([a-z_]+)\s*:\s*(.*?)\s*$")


def row_parts(text):
    """Y05: (term, keys). The keys are the last bracketed group when it ends the line and reads as pinned
    `key: value` pairs separated by semicolons; otherwise the whole text is the term."""
    match = KEY_GROUP.match(text)
    if match:
        pairs = [PAIR.match(piece) for piece in match.group(2).split(";")]
        if pairs and all(p and p.group(1) in ROW_KEYS for p in pairs):
            return match.group(1).strip(), {p.group(1): p.group(2) for p in pairs}
    return text.strip(), {}


BULLET = re.compile(r"^\s*(?:[-*+\u2022]|\d{1,3}[.)])\s*\S")
KEYED_GROUP = re.compile(r"\[\s*[a-z_]+\s*:[^\[\]]*\]\s*$", re.IGNORECASE)


def strict_rows(lines, section, title, name):
    """F04 (X09, X33, fail closed): an exclusions file is read whole or not at all. Exit 3 on a heading of the
    section's name in another form, on rows or bullets with no pinned heading, and on any line under the heading
    that is neither a row, a blank line, a comment nor a sub-heading."""
    same = re.compile(r"^#{2,6}\s*%s\b" % re.escape(title.split(" ", 1)[1]), re.IGNORECASE)
    present = False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) == 2 and line.strip().lower() == title.lower():
            present = True
        elif same.match(line.strip()):
            raise cannot(name, "line %d" % (index + 1), "a heading %r that is not the pinned %s" %
                         (line.strip(), title),
                         "one heading that reads exactly %s, with the rows under it" % title)
    if not present:
        for index, line in enumerate(lines):
            if BULLET.match(line) and line.strip() != "---":
                raise cannot(name, "line %d" % (index + 1), "a row with no %s heading above it" % title,
                             "the rows under a heading that reads exactly %s" % title)
        return
    comment = False
    for index in sorted(section):
        line = lines[index].strip()
        if comment or line.startswith("<!--"):
            comment = "-->" not in (line[4:] if line.startswith("<!--") else line)
            continue
        if not line or line.startswith("#") or line.startswith("- "):
            continue
        raise cannot(name, "line %d" % (index + 1), "a line under %s that is not a row" % title,
                     "- <term> [key: value; ...], one row per line, a hyphen and a space first")


def section_rows(text, title, name, strict=False):
    """(line number, term, keys) of every row under the level-2 heading `title`; an empty term is exit 3. With
    `strict` (the exclusions, F04), anything the reader cannot apply as a row is exit 3 too. A36 (R74): a line inside
    an HTML comment is never a row."""
    lines = text.split("\n")
    section = section_lines(lines, title)
    if strict:
        strict_rows(lines, section, title, name)
    rows, comment = [], False
    for index in sorted(section):
        line = lines[index].strip()
        # A36 (R74): a row inside a comment, on one line or over several, is an example, as strict_rows reads it
        if comment or line.startswith("<!--"):
            comment = "-->" not in (line[4:] if line.startswith("<!--") else line)
            continue
        match = ROW_LINE.match(lines[index].strip()) if lines[index].strip().startswith("- ") else None
        if not match:
            continue
        term, keys = row_parts(match.group(1))
        if strict and not keys and KEYED_GROUP.search(match.group(1)):
            raise cannot(name, "line %d" % (index + 1), "a bracketed key list with a key the row does not have",
                         "keys among %s, as key: value pairs separated by semicolons" % ", ".join(ROW_KEYS))
        if not words_of(term) and not term.strip():
            raise cannot(name, "line %d" % (index + 1), "a row with an empty term",
                         "- <term> [key: value; ...], the term first")
        rows.append((index + 1, term, keys))
    return rows


def strand_folders(run):
    base = run.root / "strands"
    try:
        return [p for p in sorted(base.iterdir()) if p.is_dir() and re.match(r"\d{3}-", p.name)] if base.is_dir() else []
    except OSError as exc:
        raise cannot("strands/", WHOLE, "cannot list the strands: %s" % exc, "a readable strands folder")


def strand_folder(run, short):
    if not re.fullmatch(r"\d{3}", short or ""):
        raise cannot("strands/", "--strand", "%r is not a strand's three-digit short id" % short, "a short id, such "
                     "as 001")
    found = [p for p in strand_folders(run) if p.name.startswith(short + "-")]
    if not found:
        raise cannot("strands/", "--strand", "no strand %s in this record" % short, "a strand's short id")
    return found[0]


class Exclusions:
    """Every strand's exclusion rows: literal names and terms (with the gaps and the fused form), and figures."""

    def __init__(self):
        self.patterns, self.figures = [], []


def load_exclusions(run):
    found = Exclusions()
    for folder in strand_folders(run):
        path = folder / "solution" / "exclusions.md"
        name = run.name(path)
        if not path.exists():
            run.absent(name)
            continue
        for line, term, keys in section_rows(run.text(path, name), HEADINGS[1], name, strict=True):
            kind = keys.get("kind")
            if kind is not None and kind not in EXCLUSION_KINDS:
                raise cannot(name, "line %d" % line, "the row kind %r is not name, term or figure" % kind,
                             "kind: name, kind: term or kind: figure")
            number = whole_number(term)
            if kind == "figure" and number is None:
                raise cannot(name, "line %d" % line, "a figure row whose term is not a number", "a figure, such as "
                             "45,000 or 45k")
            kind = kind or ("figure" if number is not None else "term")
            where = "%s line %d" % (name, line)
            if kind == "figure":
                found.figures.append((number.value, number.precision, where, term))
            else:
                regex = literal_regex(term, tokenised=True, fused=True)
                if regex is None:
                    raise cannot(name, "line %d" % line, "a row whose term has no letters or digits",
                                 "a name or a term")
                found.patterns.append(Pattern("exclusion", kind, regex, where, term, tokenised=True))
    return found


class AllowRow:
    __slots__ = ("term", "normal", "ok", "file", "line")

    def __init__(self, term, ok, file, line):
        self.term, self.normal, self.ok, self.file, self.line = term, normal_form(term), ok, file, line


NOT_YES = frozenset(("no", "not", "nope", "never", "pending", "tbc", "tbd", "todo", "ask", "asked", "awaiting",
                     "waiting", "unanswered", "unknown", "maybe", "none", "false", "n"))


def ok_granted(ok):
    """F19 (X09): an ok whose first word says no, not yet or ask is not the user's yes, so it clears nothing."""
    words = words_of(ok)
    return bool(words) and words[0] not in NOT_YES


def load_allowlist(run, short):
    """The allowlist of one strand (X10); a row without a non-empty ok clears nothing and warns on every run."""
    if short is None:
        return []
    if short in run.allowlists:
        return run.allowlists[short]
    path = strand_folder(run, short) / "solution" / "allowlist.md"
    name = run.name(path)
    rows = []
    if not path.exists():
        run.absent(name)
    else:
        for line, term, keys in section_rows(run.text(path, name), HEADINGS[2], name):
            ok = (keys.get("ok") or "").strip()
            refused = bool(ok) and not ok_granted(ok)
            row = AllowRow(term, "" if refused else ok, name, line)
            if not ok:
                run.add(record_warning(name, line, "an allowlist row without the user's ok clears nothing",
                                       "the row with ok: and the user's words, or the row removed", "allowlist"))
            elif refused:
                run.add(record_warning(name, line, "an allowlist row whose ok is not the user's yes (%s) clears "
                                       "nothing" % cut(ok), "the row with ok: and the user's words, or the row "
                                       "removed", "allowlist"))
            rows.append(row)
    run.allowlists[short] = rows
    return rows


# .docx (X35): read in memory, the body and every part that carries text, with the guards of X35 and X42.

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WORD_PART = re.compile(r"word/(?:document|header\d*|footer\d*|footnotes|endnotes|comments|people)\.xml", re.IGNORECASE)
RELS_PART = re.compile(r"(?:word/)?_rels/[^/]*\.rels", re.IGNORECASE)
UNREAD_PART = re.compile(r"(?:^|/)embeddings/|\.(?:docx|docm|dotx|dotm|htm|html|mht|mhtml|rtf|xlsx|xlsm|pptx|bin)$",
                         re.IGNORECASE)  # F08: a part Word may show that the lint does not read is exit 3
PLAIN_PART = re.compile(r"(?:^|/)printerSettings/printerSettings\d*\.bin$", re.IGNORECASE)  # R08: holds no text
ANOTHER_FILE = ("this document has another file inside it",
                "take that file out and add it as its own input, then run this again")  # R08, the user's wording
SHOWN_ATTRIBUTES = ("author", "initials", "instr", "tooltip", "descr", "title")  # F08: attribute text Word shows
PROPERTY_PARTS = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")
PREFIXES = {"http://purl.org/dc/elements/1.1/": "dc:", "http://purl.org/dc/terms/": "dcterms:",
            "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "cp:",
            "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes": "vt:"}
DTD = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)


def element_name(tag):
    if tag.startswith("{"):
        space, _, local = tag[1:].partition("}")
        return PREFIXES.get(space, "") + local
    return tag


def shown_attributes(root):
    """F08: [(label, value)] of the attributes Word shows to a reader (comment and revision authors and initials,
    field instructions such as a hyperlink's, tooltips, picture alt text and titles), in document order."""
    found = []
    for node in root.iter():
        for key, value in node.attrib.items():
            local = key.rsplit("}", 1)[-1]
            if local in SHOWN_ATTRIBUTES and value and value.strip():
                found.append(("%s %s" % (element_name(node.tag).rsplit("}", 1)[-1], local), " ".join(value.split())))
    return found


def word_paragraphs(root):
    """Each w:p as one line: w:t, w:delText and w:instrText joined with nothing, w:tab a space, w:br a break."""
    paragraphs = []

    def visit(node):
        if node.tag == W_NS + "p":
            pieces = []

            def inner(parent):
                for child in parent:
                    if child.tag == W_NS + "p":
                        visit(child)
                        continue
                    if child.tag in (W_NS + "t", W_NS + "delText", W_NS + "instrText"):
                        pieces.append(child.text or "")
                    elif child.tag == W_NS + "tab":
                        pieces.append(" ")
                    elif child.tag in (W_NS + "br", W_NS + "cr"):
                        pieces.append(" ")
                    inner(child)

            inner(node)
            paragraphs.append("".join(pieces))
            return
        for child in node:
            visit(child)

    visit(root)
    return paragraphs


def property_lines(root):
    """Each element of a property part with text as one line, named by its element (dc:creator, Company)."""
    lines, labels = [], []
    for node in root.iter():
        for value, label in ((node.get("name"), element_name(node.tag) + " name"),
                             (node.text, element_name(node.tag))):
            if value and value.strip():
                lines.append(" ".join(value.split()))
                labels.append(label)
    return lines, labels


def docx_parts(data, name):
    """[(part, lines, labels or None)] of a .docx held in memory; any guard or parse failure is exit 3."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = {info.filename: info for info in archive.infolist()}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as exc:
        raise cannot(name, WHOLE, "not a .docx (zip) archive: %s" % exc, "a Word document")
    if "word/document.xml" not in infos:
        raise cannot(name, "word/document.xml", "the archive has no word/document.xml", "a Word document")
    unread = sorted(n for n in infos if UNREAD_PART.search(n) and not PLAIN_PART.search(n))
    if unread:
        raise cannot(name, unread[0], *ANOTHER_FILE)
    wanted = ["word/document.xml"] + sorted(n for n in infos if WORD_PART.fullmatch(n) and n != "word/document.xml") \
        + [n for n in PROPERTY_PARTS if n in infos] + sorted(n for n in infos if RELS_PART.fullmatch(n))
    total, parts = 0, []
    for part in wanted:
        info = infos[part]
        total += info.file_size
        if info.file_size > DOCX_MEMBER_LIMIT or total > DOCX_TOTAL_LIMIT:
            raise cannot(name, part, "the part is larger than the lint reads (%d bytes)" % info.file_size,
                         "a part under %d bytes and an archive under %d in all" % (DOCX_MEMBER_LIMIT, DOCX_TOTAL_LIMIT))
        if info.file_size > DOCX_RATIO_FLOOR and info.compress_size and \
                info.file_size > DOCX_RATIO * info.compress_size:
            raise cannot(name, part, "the part expands more than %d to 1" % DOCX_RATIO, "an ordinary Word document")
        try:
            raw = archive.read(part)
        except (zipfile.BadZipFile, OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            raise cannot(name, part, "cannot read the part: %s" % exc, "a readable Word document")
        if DTD.search(raw) or DTD.search(raw.replace(b"\x00", b"")):  # F29: a UTF-16 part as well
            raise cannot(name, part, "the part declares a DOCTYPE or an ENTITY", "a Word part without a DTD")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise cannot(name, part, "the part is not well-formed XML: %s" % exc, "a readable Word document")
        if part in PROPERTY_PARTS:
            lines, labels = property_lines(root)
            parts.append((part, lines, labels))
        elif RELS_PART.fullmatch(part):
            targets = [" ".join(node.get("Target", "").split()) for node in root.iter()
                       if node.tag.rsplit("}", 1)[-1] == "Relationship" and node.get("TargetMode") == "External" and
                       node.get("Target", "").strip()]
            if targets:
                parts.append((part, targets, ["Relationship Target"] * len(targets)))
        else:
            if any(node.tag.rsplit("}", 1)[-1] == "altChunk" for node in root.iter()):
                raise cannot(name, part, *ANOTHER_FILE)
            lines = word_paragraphs(root)
            labels = ["paragraph %d" % (i + 1) for i in range(len(lines))]
            for label, value in shown_attributes(root):
                lines.append(value)
                labels.append(label)
            parts.append((part, lines, labels))
    return parts


# The checker: one unit of text, every rule its mode runs (X05, X37, X38), then the allowlist (X10, X39).

class Unit:
    """One text the rules check: a text file, a .docx part, or one payload string or number (X22)."""

    def __init__(self, file, text, seq, field=None, part=None, strand=None, mode="full", kind="text",
                 structural=False, raw=None, labels=None, sample=False):
        self.file, self.text, self.seq, self.field, self.part = file, text, seq, field, part
        self.strand, self.mode, self.kind, self.structural = strand, mode, kind, structural
        self.raw, self.labels, self.raw_json = raw, labels, False
        self.sample = sample  # A33 (R69): a value of an item batch, invented, so its numbers raise no warning
        self.phone = False  # A39 (R75): a phone column's value in column_values, which the id row skips
        self.label = False  # A39 (R77): a label's colour, index or position in a column's settings, never warned
        self.joins = False  # G19 (R53): whether the string is part of its payload's joined text
        self.own = (file, ("block",) if mode == "client-safe-block" else ("body", "block"))
        if mode in ("blueprint", "glossary"):
            self.own = (None, ())  # the blueprint's client-facing text feeds no set, so its own rest still counts
        self.line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]

    def where(self, offset):
        if self.kind != "text":
            return self.field, None, None
        index = max(0, bisect.bisect_right(self.line_starts, offset) - 1)
        line, column = index + 1, offset - self.line_starts[index] + 1
        if self.part:
            label = self.labels[index] if self.labels and index < len(self.labels) else "paragraph %d" % line
            return "%s %s" % (self.part, label), line, column
        return "line %d" % line, line, column

    def raw_span(self, start, end):
        if self.raw is None:
            return start, end
        last = self.raw[end - 1] + 1 if end > start else self.raw[start] if start < len(self.raw) else len(self.raw)
        return (self.raw[start] if start < len(self.raw) else last), last


PROBLEMS = {
    "term": ("a term of class %s (%s)", "the text without it: client-facing text never carries this term"),
    "phonetic": ("sounds like a term of class %s (%s)", "the text without it, or a whitelist row in the local list "
                                                       "when the word is an ordinary one"),
    "seller-account": ("names the user's own account structure (%s)", "the text without the user's own workspaces, "
                                                                      "accounts and ids"),
    "exclusion": ("a %s the client's exclusions keep out (%s)", "the text without it"),
    "internal-note": ("an internal note mark (%s)", "client-facing words only; internal notes stay in the record"),
    "credential": ("a credential shape (%s)", "no secret in anything written to monday"),
}


class Check:
    """The rules over one unit. Every hit is (rule, class, severity, start, end, problem, expected, extra)."""

    def __init__(self, run, unit):
        self.run, self.unit, self.lists, self.sets = run, unit, run.lists, run.sets
        self.text = blank_marks(unit.text)
        self.vf = fold(self.text)
        decoded = percent_decode_all(plain(self.text)) if "%" in self.text else None
        self.vfd = fold_variant(decoded) if decoded is not None and decoded.text != self.text else None
        self.tokens = tokenise(self.text, self.vf)
        self.hits = []
        self.links = link_spans(self.vf.text)

    def hit(self, rule, cls, severity, start, end, problem, expected, source=None, **extra):
        self.hits.append((rule, cls, severity, start, end, problem, expected, source, extra))

    def usable(self, entry):
        file, part = entry[0], entry[1]
        return not (file == self.unit.own[0] and part in self.unit.own[1])

    # Literal rows of every list, the firm, the seller's names, the vocabulary groups, notes, exclusions.

    def literals(self):
        if self.unit.mode == "terms":  # X31: the firm rule alone, no shipped row and no exclusion
            patterns = [p for p in self.lists.literals if p.rule == "term" and p.cls == "firm"]
        else:
            patterns = list(self.lists.literals) + list(self.run.exclusions.patterns)
        for variant_index, variant in enumerate([self.vf] + ([self.vfd] if self.vfd else [])):
            tokens = self.tokens if variant_index == 0 else tokenise(self.text, variant)
            for pattern in patterns:
                spans = [variant.span(m.start(), m.end()) for m in pattern.regex.finditer(variant.text)]
                spans += [span for span in token_matches(tokens, pattern.forms) if not overlaps(spans, *span)]
                for start, end in spans:
                    if pattern.rule == "term":
                        problem = PROBLEMS["term"][0] % (pattern.cls, pattern.origin)
                        expected = PROBLEMS["term"][1]
                    elif pattern.rule == "seller-account":
                        problem, expected = PROBLEMS["seller-account"][0] % pattern.origin, PROBLEMS["seller-account"][1]
                    elif pattern.rule == "exclusion":
                        problem, expected = PROBLEMS["exclusion"][0] % (pattern.cls, pattern.origin), \
                            PROBLEMS["exclusion"][1]
                    else:
                        problem, expected = PROBLEMS["internal-note"][0] % pattern.term, PROBLEMS["internal-note"][1]
                    cls = "seller-account" if pattern.rule == "seller-account" else pattern.cls
                    self.hit(pattern.rule, cls, "block", start, end, problem, expected,
                             pattern.origin.split(" line ")[0] if pattern.rule == "exclusion" else None)

    # re: rows line by line, on the line as written, with backslashes as slashes, percent-decoded and folded (X03).

    def lines(self):
        position = 0
        for line in self.text.split("\n"):
            yield position, line
            position += len(line) + 1

    def variants_of(self, start, line):
        base = plain(line, start)
        found = [base]
        if "\\" in line:
            found.append(slashed(base))
        if "%" in line:
            decoded = percent_decode_all(base)
            found += [decoded, slashed(decoded)]
        folded = fold_variant(base)
        if folded.text != line.lower():
            found.append(folded)
            if "\\" in folded.text:  # F12: a full-width backslash folds to one
                found.append(slashed(folded))
        return found

    def regex_rows(self):
        id_row = self.lists.id_row
        for start, line in self.lines():
            if not line.strip():
                continue
            variants = self.variants_of(start, line)
            masked = None
            for row in self.lists.regexes:
                if self.unit.mode == "terms" and row.cls != "firm":
                    continue
                is_id = row is id_row
                if is_id and (self.unit.structural or self.unit.raw_json or self.unit.phone):  # A39 (R75)
                    continue
                if is_id and masked is None:  # F31: only a link with a scheme hides its ids
                    masked = [Variant(mask(v.text, real_links(v.text)), v.offsets) for v in variants]
                for variant in (masked if is_id else variants):
                    for begin, finish in windows(len(variant.text)):
                        if is_id:
                            for match in ID_WIDE.finditer(variant.text, begin, finish):
                                self.id_hit(variant, match, row)
                        for match in row.regex.finditer(variant.text, begin, finish):
                            if match.end() == match.start():
                                continue
                            if is_id:
                                self.id_hit(variant, match, row)
                                continue
                            s, e = variant.span(match.start(), match.end())
                            self.hit("term", row.cls, "block", s, e, PROBLEMS["term"][0] % (row.cls, row.where()),
                                     PROBLEMS["term"][1])

    def id_hit(self, variant, match, row):
        """The id row's hit, unless (F27) the digits follow a decimal point, as a coordinate's do, or are eight digits
        that read as a date from 1900 to 2099 (YYYYMMDD), which warns as a date in split form does (Y02)."""
        kind = id_kind(variant.text, match.start(), match.end())
        if kind == "decimal":
            return
        s, e = variant.span(match.start(), match.end())
        if kind == "date":
            self.hit("split-figure", None, "warn", s, e, "a date written as eight digits, or an id that reads as one",
                     "the date written with its separators, such as 2026-11-03")
            return
        self.hit("term", row.cls, "block", s, e, PROBLEMS["term"][0] % (row.cls, row.where()), PROBLEMS["term"][1])

    def number_id(self):
        """Y08, F02: a JSON number outside a structural key is checked by the id row as its decimal text, so an id
        written as a number, a float or with a sign blocks as it does in a string."""
        id_row = self.lists.id_row
        if self.unit.structural or id_row is None:
            return
        for match in ID_WIDE.finditer(self.vf.text):
            self.id_hit(self.vf, match, id_row)

    def notes_and_credentials(self):
        lines = list(self.lines())
        for index, (start, line) in enumerate(lines):
            if not line.strip():
                continue
            match = re.match(FRONT_MATTER_LINE, line)
            if match:
                self.hit("internal-note", None, "block", start, start + match.end(), PROBLEMS["internal-note"][0] %
                         "a front-matter line", PROBLEMS["internal-note"][1])
            if line.strip() == "---" and front_matter_schema(lines, index):
                s = start + line.index("-")
                self.hit("internal-note", None, "block", s, s + 3, PROBLEMS["internal-note"][0] %
                         "a front-matter block", PROBLEMS["internal-note"][1])
            folded = fold_variant(plain(line, start))
            for match in re.finditer(SPEAKER_LABEL, folded.text):
                s, e = folded.span(match.start(), match.end())
                self.hit("internal-note", None, "block", s, e, PROBLEMS["internal-note"][0] % "a speaker label",
                         PROBLEMS["internal-note"][1])
            self.credentials(line, start, lines[index + 1] if index + 1 < len(lines) else None)

    def credentials(self, line, start, after):
        """X15's shapes on the line as written, its percent-decoded copy and its folded copy (F12), the looser pairs
        whose value looks like a secret, a key at a line's end with its value on the next line (F10), and shape 6."""
        variants = [plain(line, start)]
        if "%" in line:
            variants.append(percent_decode_all(variants[0]))
        folded = fold_variant(variants[0])
        if folded.text != line.lower():  # F12: a look-alike, a full-width mark or an invisible character
            variants.append(folded)
        for variant in variants:
            found = []
            for shape, pattern, flags in CREDENTIAL_SHAPES:
                for match in re.finditer(pattern, variant.text, flags):
                    found.append(match.span())
                    s, e = variant.span(match.start(), match.end())
                    self.hit("credential", None, "block", s, e, PROBLEMS["credential"][0] % shape,
                             PROBLEMS["credential"][1])
            for match in re.finditer(LOOSE_SECRET, variant.text, re.IGNORECASE):
                if secretish(match.group("value")) and not overlaps(found, match.start(), match.end()):
                    s, e = variant.span(match.start(), match.end())
                    self.hit("credential", None, "block", s, e, PROBLEMS["credential"][0] % "a secret pair",
                             PROBLEMS["credential"][1])
            outside = mask(variant.text, link_spans(variant.text))
            for match in re.finditer(LONG_SECRET, outside):
                value = match.group()
                if any(c.isdigit() for c in value) and any(c.islower() for c in value) and \
                        any(c.isupper() for c in value):
                    s, e = variant.span(match.start(), match.end())
                    self.hit("credential", None, "block", s, e, PROBLEMS["credential"][0] % "a long mixed string",
                             PROBLEMS["credential"][1])
        if after is not None and re.search(SECRET_AT_END, folded.text, re.IGNORECASE):
            after_start, after_line = after
            value = re.match(r"[ \t]*([^\s]{4,})", after_line)
            if value and secretish(value.group(1)):
                s = after_start + value.start(1)
                self.hit("credential", None, "block", s, s + len(value.group(1)), PROBLEMS["credential"][0] %
                         "a secret pair across a line break", PROBLEMS["credential"][1])

    def seller_ids(self):
        for variant in [self.vf] + ([self.vfd] if self.vfd else []):
            for regex, form, field in self.lists.seller_ids:
                for match in regex.finditer(variant.text):
                    s, e = variant.span(match.start(), match.end())
                    self.hit("seller-account", "seller-account", "block", s, e,
                             PROBLEMS["seller-account"][0] % ("%s %s" % (SETTINGS_NAME, field)),
                             PROBLEMS["seller-account"][1])

    # The phonetic rule (X32, Y09) with its whitelist.

    def phonetic(self):
        sources = self.lists.phonetic
        if self.unit.mode == "terms":
            sources = [source for source in sources if source.cls == "firm"]
        if not sources or not self.tokens:
            return
        words = [t.word for t in self.tokens]
        keys = [phonetic_key(w) for w in words]
        spelled = [letters(w) for w in words]
        literal = [(h[3], h[4], h[1]) for h in self.hits if h[0] == "term"]
        found = []
        for source in sources:
            cleared = self.whitelist_spans(source.whitelist)
            sizes = sorted({1, len(source.words), len(source.words) + 1})
            for size in sizes:
                for i in range(len(self.tokens) - size + 1):
                    group = self.tokens[i:i + size]
                    if group[0].paragraph != group[-1].paragraph:
                        continue
                    joined = "".join(spelled[i:i + size])
                    if len(joined) < 4:
                        continue
                    if size == 1:
                        candidate = {keys[i]}
                    else:
                        candidate = {" ".join(keys[i:i + size]), "".join(keys[i:i + size])}
                    near = source.limit and edit_distance(joined, source.letters, source.limit) <= source.limit
                    if not (candidate & source.keys or near):
                        continue
                    # A36 (R72): a near sound of the firm made only of ordinary words ("real names", "call more") is
                    # an everyday phrase, not the firm; the firm's own letters, spaced or fused, and every literal
                    # form of its name and renderings still block.
                    if source.cls == "firm" and joined != source.letters and all(map(ordinary, words[i:i + size])):
                        continue
                    span = (i, i + size)
                    shown = normal_form(self.text[group[0].start:group[-1].end])
                    if any(shown == normal_form(term) for term in source.whitelist) or \
                            any(a <= span[0] and span[1] <= b for a, b in cleared):
                        continue
                    start, end = group[0].start, group[-1].end
                    if any(s < end and start < e and c == source.cls for s, e, c in literal):
                        continue
                    found.append((start, end, source))
        found.sort(key=lambda f: (f[0], -f[1]))
        merged = []
        for start, end, source in found:
            if merged and merged[-1][2].cls == source.cls and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]), merged[-1][2])
                continue
            merged.append((start, end, source))
        for start, end, source in merged:
            self.hit("phonetic", source.cls, "block", start, end, PROBLEMS["phonetic"][0] % (source.cls, source.origin),
                     PROBLEMS["phonetic"][1])

    def whitelist_spans(self, terms):
        """Token ranges of every occurrence of a whitelist row in the text."""
        spans, words = [], [t.word for t in self.tokens]
        for term in terms:
            target = words_of(term)
            for i in range(len(words) - len(target) + 1):
                if target and words[i:i + len(target)] == target:
                    spans.append((i, i + len(target)))
        return spans

    # The paraphrase rule (X06): a cue phrase and a person reference in one sentence.

    def paraphrase(self):
        sentences = {}
        for token in self.tokens:
            sentences.setdefault(token.sentence, []).append(token)
        for sentence in sentences.values():
            words = [t.word for t in sentence]
            cues = []
            for i, word in enumerate(words):
                for group, phrase in cue_index().get(word, ()):
                    if tuple(words[i:i + len(phrase)]) == phrase:
                        cues.append((group, i, i + len(phrase)))
            if not cues:
                continue
            used = {k for _, a, b in cues for k in range(a, b)}
            kinds = {i: self.person(sentence, i) for i in range(len(sentence)) if i not in used}
            names = [sentence[i] for i, kind in sorted(kinds.items()) if kind == "name"]
            people = [sentence[i] for i, kind in sorted(kinds.items()) if kind]
            if not people:
                continue
            cues.sort(key=lambda c: (c[1], -(c[2] - c[1])))
            kept = []
            for group, a, b in cues:
                if any(g == group and x <= a and b <= y for g, x, y in kept):
                    continue
                if " ".join(words[a:b]) in NAME_ONLY_CUES and not names:
                    continue
                kept.append((group, a, b))
            who = self.text[(names or people)[0].start:(names or people)[0].end]
            for group, a, b in kept:
                self.hit("paraphrase", group, "block", sentence[a].start, sentence[b - 1].end,
                         "a remark about a person (%s): the cue %r beside %r" %
                         (group, self.text[sentence[a].start:sentence[b - 1].end], who),
                         "the point made about the work, with no person's stakes, health, plans or standing")

    def person(self, sentence, index):
        """"name" for a person's name, "role" for a role word anchored to one person, else None (X06, F24)."""
        token = sentence[index]
        if self.named(token):
            return "name"
        role = token.word in ROLE_SINGLE or (index + 1 < len(sentence) and
                                              (token.word, sentence[index + 1].word) in ROLE_PAIRS)
        if not role:
            return None
        before = sentence[max(0, index - 2):index]
        if any(t.word in POSSESSIVES or self.text[t.end - 2:t.end] in ("'s", "\u2019s") for t in before):
            return "role"
        beside = sentence[max(0, index - 1):index] + sentence[index + 1:index + 2]
        if any(t.cap and t.word not in COMMON_WORDS and t.word not in PRONOUNS and t.word not in STOP_WORDS and
               not t.word.isdigit() for t in beside):
            return "role"
        return None

    def named(self, token):
        return token.cap and not token.first and not token.word.isdigit() and token.word not in COMMON_WORDS and \
            token.word not in PRONOUNS and token.word not in STOP_WORDS

    # Figures, split renderings, numbers and split ids (X25, X34, Y02, Y08).

    def figure_pools(self):
        sets = self.sets
        keep = [e for e in sets.cost if self.usable(e[2:])], [e for e in sets.cost_percent if self.usable(e[2:])], \
            [e for e in sets.record if self.usable(e[2:])], [e for e in sets.record_percent if self.usable(e[2:])]
        return keep

    def numbers(self):
        if self.unit.structural:
            return
        summary = self.unit.mode == "summary"
        cost, cost_percent, record, record_percent = self.figure_pools()
        exclusions = self.run.exclusions.figures
        text = self.vf.text
        dates = date_spans(text)
        chains = [] if self.unit.kind == "number" else digit_chains(text, dates)
        date_chains = [(c[0][0], c[-1][1]) for c in chains if chain_is_date(text, c)]
        reported = set()
        for chain in chains:
            start, end = self.vf.span(chain[0][0], chain[-1][1])
            if chain_is_date(text, chain):
                self.hit("split-figure", None, "warn", start, end, "a date written with its digits split",
                         "the date written whole, such as 2026-11-03")
                continue
            value = Fraction(int("".join(text[s:e] for s, e in chain)))
            self.split_match(value, Fraction(1), start, end, cost, record, exclusions)
        for variant_index, variant in enumerate([self.vf] + ([self.vfd] if self.vfd else [])):
            for number in parse_numbers(variant, self.text):
                start, end = variant.span(number.start, number.end)
                if variant_index == 0 and overlaps(date_chains, number.start, number.end):
                    continue
                if number.split:
                    self.split_match(number.value, number.precision, start, end, cost, record, exclusions)
                    continue
                if summary:
                    continue
                key = (start, number.value)
                if key in reported:
                    continue
                reported.add(key)
                in_link = inside(self.links, number.start, number.end) if variant_index == 0 else True
                self.classify(number, start, end, in_link or variant_index > 0, cost, cost_percent, record,
                              record_percent, exclusions)

    def split_match(self, value, precision, start, end, cost, record, exclusions):
        probe = Number(value, precision, 0, 0)
        for figure, fprec, where, _ in exclusions:
            if probe.matches(figure, fprec):
                self.hit("split-figure", None, "block", start, end, "an excluded figure written in split form (%s)" %
                         where, "the text without the figure", where.split(" line ")[0])
                return
        if value < SMALL_FIGURE:  # A33 (R67): a count or a label, never a client figure
            return
        for figure, fprec, file, _ in cost:
            if probe.matches(figure, fprec):  # A34 (R70): the client's own figure warns in its own build
                self.hit("split-figure", None, "warn", start, end, "the client figure %s written in split form" %
                         show(figure), OWN_FIGURE_EXPECTED, file)
                return
        if self.unit.sample or self.unit.label:  # A33 (R69): a sample row's numbers are invented, and A39 (R77) a
            return  # label colour is a setting, so neither is warned as a record number
        for figure, fprec, file, _ in record:
            if probe.matches(figure, fprec):
                self.hit("split-figure", None, "warn", start, end, "a number of the client record written in split "
                         "form", "check it is meant for the client; it is reported and kept", file)
                return

    def classify(self, number, start, end, in_link, cost, cost_percent, record, record_percent, exclusions):
        for figure, fprec, where, _ in exclusions:
            if number.matches(figure, fprec):
                self.hit("exclusion", "figure", "block", start, end, PROBLEMS["exclusion"][0] % ("figure", where),
                         PROBLEMS["exclusion"][1], where.split(" line ")[0])
                break
        # A33 (R69): a sample row's numbers are invented (A28), so they are warned neither as record numbers nor as
        # numbers to check; its exclusions still block on them, and the client's cost figures and percentages warn
        # on them as anywhere else in the build (A34, R70). A39 (R77): a label's colour, index or position in a status
        # or dropdown column's settings is quiet the same way, and its exclusions and the client's cost figures stay.
        quiet = in_link or (number.plain and number.value >= 10 ** 7) or self.unit.sample or self.unit.label
        if number.percent:
            for figure, fprec, file, _ in cost_percent:
                if number.matches(figure, fprec):
                    return self.hit("figure", None, "warn", start, end, "matches the client's cost percentage %s%% "
                                    "(%s)" % (show(figure), file), OWN_FIGURE_EXPECTED, file)
            if number.value < 10 or quiet:
                return None
            for figure, fprec, file, _ in record_percent:
                if number.matches(figure, fprec):
                    return self.record_warning(start, end, file)
            return self.number_warning(start, end)
        if number.value < SMALL_FIGURE:  # A33 (R67): a count or a label, never a client figure, and never warned
            return None
        matched = [f for f in cost if number.matches(f[0], f[1])]
        large = [f for f in matched if f[0] >= 1000]
        if large:  # A34 (R70): the client's own figure warns in its own build; the wall and the exclusions block
            return self.hit("figure", None, "warn", start, end, "matches the client's cost figure %s (%s)" %
                            (show(large[0][0]), large[0][2]), OWN_FIGURE_EXPECTED, large[0][2])
        if matched and (number.cue or number.currency or number.rate):
            return self.hit("figure", None, "warn", start, end, "matches the client's cost figure %s beside a cost "
                            "word (%s)" % (show(matched[0][0]), matched[0][2]), OWN_FIGURE_EXPECTED, matched[0][2])
        if quiet or number.value < 10:
            return None
        if matched:
            return self.record_warning(start, end, matched[0][2], "matches a client figure with no cost word beside it")
        for figure, fprec, file, _ in record:
            if number.matches(figure, fprec):
                return self.record_warning(start, end, file)
        return self.number_warning(start, end)

    def record_warning(self, start, end, file, problem="matches a number of the client record"):
        self.hit("record-number", None, "warn", start, end, problem + " (%s)" % file,
                 "flag, do not remove: check it is meant for the client", file)

    def number_warning(self, start, end):
        self.hit("number", None, "warn", start, end, "a number that matches no figure of the client record",
                 "check the number is meant for the client")

    def split_ids(self):
        if self.unit.structural or self.unit.raw_json or self.unit.kind == "number":
            return
        text = self.vf.text
        for chain in id_chains(text):
            s, e = chain[0][0], chain[-1][1]
            if chain_is_date(text, chain) or inside(self.links, s, e):
                continue
            start, end = self.vf.span(s, e)
            self.hit("term", "id-patterns", "block", start, end, "an id or a phone number written in digit groups "
                     "(split id, X34)", PROBLEMS["term"][1])

    # Quotes, copied runs and near copies (X19, X24, X36, X37).

    def runs_and_quotes(self):
        words = [t.word for t in self.tokens]
        sets, summary = self.sets, self.unit.mode == "summary"
        covered = set()
        for a, b, file in stretches(self.grams(words, QUOTE_WORDS, lambda g: [
                e[0] for e in sets.quotes.get(g, ()) if self.usable(e)])):
            covered.update(range(a, b))
            self.hit("quote", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "eight or more words of a "
                     "client quote (%s)" % file, "the point in new words: a client's own words stay in the record",
                     file)
        if len(words) >= NEAR_WORDS - 1 and sets.quote_tokens:  # F15: a quote with one word changed, dropped or added
            for a, b, file in stretches(self.near_windows(words, "quotes", self.usable, lambda keys: False)):
                if any(k in covered for k in range(a, b)):
                    continue
                covered.update(range(a, b))
                self.hit("quote", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "eight words that "
                         "match a client quote's but for one word (%s)" % file, "the point in new words: a client's "
                         "own words stay in the record", file, near=True)
        if self.unit.mode in ("client-safe-block", "glossary"):
            return  # X36, X38, L163: a client-safe block and the blueprint's glossary are exempt from runs only

        def runs_usable(entry):
            return self.usable(entry) and not (summary and SUMMARY_FILE.fullmatch(entry[0]))

        # A36 (R73): in a payload, a run that the strand's frozen revision plans as a value (a label list, a view's
        # name, a column's values) is not copied from that strand's blueprint files; every other source still counts.
        plan = frozen_plan(self.run, self.unit.strand) if self.run.command == "payload" and self.unit.strand else None

        def planned(entries, gram, lookups=()):
            if plan is None or not entries or not plan.holds(gram, lookups):
                return entries
            return [e for e in entries if not (kind_of(e[0]) == "blueprint" and path_strand(e[0]) == self.unit.strand)]

        def exact(gram):
            if distinct(gram) < RUN_MIN_DISTINCT:
                return []
            entries = planned([e for e in sets.runs.get(gram, ()) if runs_usable(e)], gram)
            if not entries:
                return []
            conflict = [e for e in entries if e[2]]
            if conflict:
                return [conflict[0][0]]
            if any(self.usable(e) for e in sets.docs.get(gram, ())):
                return []
            return [entries[0][0]]

        for a, b, file in stretches(self.grams(words, RUN_WORDS, exact)):
            if any(k in covered for k in range(a, b)):
                continue
            covered.update(range(a, b))
            self.hit("copied-run", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "six or more words "
                     "copied from an internal file (%s)" % file, "new words: internal text never reaches the client",
                     file)
        if len(words) < NEAR_WORDS - 1:
            return

        def in_docs(lookups):
            return any(self.usable(e) for which, key in lookups for e in sets.index("docs", which).get(key, ()))

        for a, b, file in stretches(self.near_windows(words, "runs", runs_usable, in_docs, planned)):
            if any(k in covered for k in range(a, b)):
                continue
            self.hit("copied-run", None, "block", self.tokens[a].start, self.tokens[b - 1].end, "eight words that "
                     "match an internal file's in seven places (%s)" % file, "new words: internal text never reaches "
                     "the client", file, near=True)

    def near_windows(self, words, which, usable, exempt, planned=None):
        """X24, F14, F15: the windows of the checked words that are one word away from a window of R or Q: eight
        words with one changed (in place, or with one left out on each side), or seven words that drop one. A
        conflict row wins, then the client-document text exempts (runs only), then the source blocks. A36 (R73):
        `planned(entries, window, lookups)` first drops the sources a planned value of the frozen revision covers."""
        sub, dele = self.sets.index(which, "sub"), self.sets.index(which, "del")
        found = []
        for size in (NEAR_WORDS, NEAR_WORDS - 1):
            for i in range(len(words) - size + 1):
                gram = tuple(words[i:i + size])
                if distinct(gram) < RUN_MIN_DISTINCT:
                    continue
                if size == NEAR_WORDS:
                    places = positions(which == "quotes")
                    lookups = [("sub", (p,) + gram[:p] + gram[p + 1:]) for p in places] + \
                        [("del", gram[:p] + gram[p + 1:]) for p in places]
                else:
                    lookups = [("del", gram)]
                entries = [e for kind, key in lookups for e in (sub if kind == "sub" else dele).get(key, ())
                           if usable(e)]
                if planned is not None:
                    entries = planned(entries, gram, lookups)
                if not entries:
                    continue
                conflict = [e for e in entries if len(e) > 2 and e[2]]
                if conflict:
                    found.append((i, i + size, conflict[0][0]))
                    continue
                if exempt(lookups):
                    continue
                found.append((i, i + size, sorted(entries)[0][0]))
        return sorted(found)

    @staticmethod
    def grams(words, size, lookup):
        found = []
        for i in range(len(words) - size + 1):
            result = lookup(tuple(words[i:i + size]))
            if result:
                found.append((i, i + size, result[0]))
        return found

    def execute(self):
        unit, mode = self.unit, self.unit.mode
        if mode == "wall":
            self.hits += wall_hits(self.run, self)
            return self.hits
        if mode == "terms":  # X31: the firm rule and the wall's digests and slugs
            self.literals()
            self.regex_rows()
            self.phonetic()
            self.hits += wall_hits(self.run, self)
            return self.hits
        if unit.kind == "number":
            self.numbers()
            self.seller_ids()
            self.number_id()
            self.hits += wall_hits(self.run, self)
            return self.hits
        if mode != "summary":
            self.literals()
            self.regex_rows()
            self.notes_and_credentials()
            self.seller_ids()
            self.phonetic()
            self.paraphrase()
            self.split_ids()
        self.numbers()
        if mode not in ("blueprint", "glossary"):
            # A33 (R68): the blueprint never goes to a client in v1 and restates the client's own facts by design,
            # so its prose meets no copied-run or quote rule; every string written to monday still does (payload).
            self.runs_and_quotes()
        if mode != "summary":
            self.hits += wall_hits(self.run, self)
        return self.hits


def id_kind(text, start, end):
    """F27: "decimal" for digits after a decimal point that follows a digit, "date" for eight digits that form a
    real YYYYMMDD date from 1900 to 2099, else None (an id)."""
    if start >= 2 and text[start - 1] == "." and text[start - 2].isdigit():
        return "decimal"
    digits = text[start:end]
    if len(digits) == 8 and digits.isdigit() and valid_date(digits[:4], digits[4:6], digits[6:]):
        return "date"
    return None


def secretish(value):
    """F10: a value that looks like a secret rather than a word: a digit, a capital after a small letter, or a mark
    such as . @ _ / inside it (a passphrase's hyphens too, when no space breaks it)."""
    value = value.strip(".,;:!?)]}>" + QUOTES)
    if len(value) < 4 or value.lower() in COMMON_WORDS:
        return False
    if any(c.isdigit() for c in value) or re.search(r"[a-z][A-Z]", value):
        return True
    return bool(re.search(r"[^\W\d][._@/\\#$%^&*+=~!-][^\W\d]", value)) and not re.fullmatch(r"[A-Za-z]+-[A-Za-z]+",
                                                                                                 value)


SUMMARY_FILE = re.compile(r"strands/\d{3}-[^/]+/SUMMARY\.md")
_CUES = {}


def cue_index():
    """{first word: [(group, phrase words)]} of the paraphrase cues, longest phrases first."""
    if not _CUES:
        for group, phrases in PARAPHRASE_CUES:
            for phrase in phrases:
                words = tuple(words_of(phrase))
                _CUES.setdefault(words[0], []).append((group, words))
        for value in _CUES.values():
            value.sort(key=lambda item: -len(item[1]))
    return _CUES


ROLE_SINGLE = frozenset(r for r in ROLE_WORDS if " " not in r)
ROLE_PAIRS = frozenset(tuple(r.split()) for r in ROLE_WORDS if " " in r)


def distinct(gram):
    return sum(1 for word in gram if word.isdigit() or word not in COMMON_WORDS)


def stretches(found):
    """Overlapping or adjacent windows merged into maximal stretches, each named by its first window's source."""
    merged = []
    for start, end, source in found:
        if merged and start <= merged[-1][1] - 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]), merged[-1][2])
        else:
            merged.append((start, end, source))
    return merged


def windows(size):
    """X42: a line longer than 10,000 characters is read in windows of 10,000 overlapping by 200."""
    if size <= LINE_WINDOW:
        return [(0, size)]
    return [(begin, min(size, begin + LINE_WINDOW)) for begin in range(0, size, LINE_WINDOW - LINE_OVERLAP)]


def show(value):
    value = Fraction(value)
    if value.denominator == 1:
        return "{:,}".format(int(value))
    return "{:,}".format(float(value))


# The cross-client wall (U1; X01, X02, X21, X25 to X31, X45, X46). Each record publishes into <home>/clients-index.json
# the hashes of its names, its exclusion terms, the phonetic keys of its names and its distinctive cost figures. A
# checked text blocks with rule wall on a candidate whose hash is in another record's entry, or that is another
# folder's slug, and that this record's own set O does not hold. One cutter, wall/1, serves every side.

INDEX_NAME = "<home>/clients-index.json"
LIST_FIELDS = INDEX_FIELDS[6:10]  # names, phonetic, terms, figures
HEX32 = re.compile(r"[0-9a-f]{32}")
UTC_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
CALENDAR_WORDS = frozenset("""monday tuesday wednesday thursday friday saturday sunday january february march april
may june july august september october november december""".split())
WALL_JOINERS = frozenset(("of", "and", "the", "de"))  # X26 step 2: they may join two capitalised tokens
# A39 (R76): what an index entry does not publish as a name, though X26 step 5 keeps it. A harvested run that
# starts or ends with one of FUNCTION_WORDS, written in lower or title case, is a sentence's words around a name
# (And the CRM, The Installed, An AI, So Tallowmere); the name inside it is a candidate of its own. A word made
# of one to three letters and then digits (CODE_WORD) is a key or a code of the record's own plan (P2, C10, AS1,
# A37), not a name, and so is a run that holds one. EVERYDAY_WORDS, beside the common words and the shared/ words,
# are the ordinary words a record capitalises without naming anything: compass and time-zone words, number words,
# month abbreviations, holidays, the words of a transcript's header and speaker labels, and the words a speaker
# starts a sentence with.
FUNCTION_WORDS = frozenset("""
a an the this that these those some any each every all both either neither no not i me my mine we us our ours you
your yours he him his she her hers it its they them their theirs there here who whom whose what which why how where
when whenever while whether if then than so and or but nor yet because as though although unless until since of in
on at to for from by with into onto upon about over under after before between through during without within is are
was were be been being am do does did has have had ill im ive id youre youll youve youd hes shes thats theres theyre
theyll theyve weve wed dont doesnt didnt cant wont isnt arent wasnt werent wouldnt couldnt shouldnt lets whats hi
hello hey yes oh ok okay well yeah yep
""".split())
CODE_WORD = re.compile(r"[a-z]{1,3}\d{1,4}")
GENERIC_WORDS = STOP_WORDS | CALENDAR_WORDS  # titles, acronyms, days and months: a run of everyday words holding one
EVERYDAY_WORDS = frozenset("""
north south east west central northern southern eastern western northeast northwest southeast southwest northeastern
northwestern southeastern southwestern midwest midwestern pacific mountain atlantic
twelve fifteen sixteen seventeen eighteen nineteen thirty fifty sixty seventy eighty ninety billion dozen sixth
seventh eighth ninth tenth eleventh twelfth thirtieth hundredth
feb apr aug sept oct
christmas thanksgiving easter halloween hanukkah diwali ramadan
participant participants recorder hosts attendee interviewer moderator facilitator administrator
yeah yep yup nope hi hey hiya bye goodbye sorry cheers huh hmm um uh er erm ah oops wow absolutely definitely totally
basically literally obviously officially unofficially realistically accurately apparently seriously frankly
understood cool lovely brilliant wonderful fantastic awesome funny thatll thatd wholl
""".split())
RUN_BREAK = re.compile(r"[.!?][\"'”’)\]]*\s|\n[ \t]*\n")  # a sentence end or a blank line ends a run (X27)
# Tokens joined with no space are also fused (X27 type 3). G03: so are the halves of a word broken by a hyphen at a
# line end, with spaces or tabs around the break, and a word broken by Markdown marks (X24 makes them separators
# for the word rules; the wall fuses across them). Both forms keep the spaced twin as well.
FUSE_GAP = re.compile(r"[-._@/&+]{1,3}|-[ \t]*\r?\n[ \t]*|[*_~`]+")
HARVEST_GAP = re.compile(r"[ \t]+|[ \t]*[-&+][ \t]*")  # what may sit between two words of one harvested name
INITIAL_GAP = re.compile(r"[ \t]*['\u2019\u2018`][ \t]*|[ \t]+")  # G12: between an initial and its word (O’ Rourke)
INITIALS_GAP = re.compile(r"\.?[ \t]*")  # G25: between two letters of initials (T F M, T. F. M.)
EMAIL = re.compile(r"[a-z0-9][a-z0-9._%+-]*@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
TERMS_EXT = (".md", ".txt", ".json", ".py", ".yml", ".yaml", ".csv", ".html", ".xml", ".toml", ".ini", ".cfg")
TERMS_SKIP = (".git", "__pycache__")
TERMS_SKIP_PARTS = [(name,) for name in TERMS_SKIP]  # a folder skipped by its real name
WALL_PROBLEMS = {"name": "matches a name of another client record under the home",
                 "term": "matches a term of another client record under the home",
                 "figure": "matches a figure of another client record under the home",
                 "slug": "matches the folder name of another client record under the home"}
WALL_EXPECTED = "the text without it: another client's names, terms and figures never reach this client"
_KEY_CACHE = {}


digest = mc.digest  # X02, X28: sha256 of the prefixed normal form, 128 bits; one implementation with mc.slug_key (R39)


def word_key(word):
    key = _KEY_CACHE.get(word)
    if key is None:
        key = _KEY_CACHE[word] = phonetic_key(word)
    return key


def wall_cut(text, folded=None, tokens=None):
    """wall/1's cut of one text (X27, X28): its tokens and the gap of folded text between each two of them."""
    if folded is None:
        folded = fold(text)
    if tokens is None:
        tokens = tokenise(text, folded)
    return tokens, [folded.text[a.fend:b.fstart] for a, b in zip(tokens, tokens[1:])]


def wall_candidates(tokens, gaps):
    """X27 types 1 to 3 as (first token, end token, form, fused): every token of three or more characters and
    every two-letter token written in capitals; every run of two to four tokens across commas and single line
    breaks but not across a sentence end or a blank line; and the fused forms of tokens joined with no space."""
    found = []
    for i, token in enumerate(tokens):
        if len(token.word) >= 3 or (len(token.word) == 2 and token.upper):
            found.append((i, i + 1, token.word, False))
        spaced = fused = True
        for j in range(i + 1, min(len(tokens), i + 4)):
            gap = gaps[j - 1]
            spaced = spaced and not RUN_BREAK.search(gap)
            fused = fused and bool(FUSE_GAP.fullmatch(gap))
            if not (spaced or fused):
                break
            words = [t.word for t in tokens[i:j + 1]]
            if spaced:
                found.append((i, j + 1, " ".join(words), False))
            if fused:
                found.append((i, j + 1, "".join(words), True))
    return found


def wall_keys(words, joined=False):
    """X27 type 4 and Y09: a run's key is its words' keys joined by a space (and, for an index entry, also joined
    end to end, so a fused spelling of the name keys the same); a single word has a key only at seven letters or
    more."""
    keys = [word_key(w) for w in words]
    if len(words) == 1:
        return {keys[0]} if keys[0] and len(letters(words[0])) >= 7 else set()
    if not all(keys):
        return set()
    return {" ".join(keys), "".join(keys)} if joined else {" ".join(keys)}


def plural_stems(word):
    """G12 (R43): the singular a plural or plural-possessive shape may stand for, the checked side only: a trailing s
    removed, and es after s, x, z, ch or sh; a word ending in ss, or a stem under three characters, gives none."""
    if len(word) < 4 or word[-1] != "s" or word[-2] == "s" or not word[-2].isalpha():
        return ()
    if word.endswith("es") and len(word) >= 5 and word[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return word[:-1], word[:-2]
    return (word[:-1],)


def plural_forms(word):
    """G18 (R50): the plural shapes R43's plural_stems would read as this word, s or es added, so the harvest drops
    a single word whose plural is a stop word as it drops a plural of one (R47); a possessive is the word itself or
    its plural once X24 has removed the apostrophe."""
    return [form for form in (word + "s", word + "es") if word in plural_stems(form)]


def inflection_stems(word):
    """G16 (R47): the words a plural or inflected form may stand for, which the harvest drops with its stop words:
    R43's plural stems, ies as y, and ed or ing removed, with a final e restored or a doubled letter undone. A stem
    under three characters gives none."""
    stems = set(plural_stems(word))
    if len(word) >= 5 and word.endswith("ies"):
        stems.add(word[:-3] + "y")
    for ending in ("ed", "ing"):
        if word.endswith(ending):
            stem = word[:-len(ending)]
            stems.update((stem, stem + "e"))
            if len(stem) >= 2 and stem[-1] == stem[-2]:
                stems.add(stem[:-1])
    return {stem for stem in stems if len(stem) >= 3}


def lower_words(text, alt=False):
    """G16 (R47): the words a D text writes in lower case as prose: a token with no capital letter that is joined to
    neither neighbour by a fuse gap (X27 type 3), by no gap at all or across a backtick, so the parts of an e-mail
    address, a link, a joined name or a code word are not counted."""
    tokens, gaps = wall_cut(text, fold(text, alt=alt))
    found = set()
    for i, token in enumerate(tokens):
        shown = text[token.start:token.end]
        if token.cap or any(c.isupper() for c in shown) or not token.word[:1].isalpha():
            continue
        if any(not gap or FUSE_GAP.fullmatch(gap) or "`" in gap for gap in gaps[max(0, i - 1):i + 1]):
            continue
        found.add(token.word)
    return found


def half_up(value):
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def figure_forms(value, floor, top=9):
    """X25: the n of f:<n>e<k> for k from 0 to `top` (9 unless given), the value divided by 10^k both truncated and
    rounded, where n keeps `floor` or more (100 for three digits of a cost figure, 1 for an exclusion figure and
    for O)."""
    forms = set()
    for k in range(min(top, 9) + 1):
        scaled = Fraction(value) / 10 ** k
        for n in (scaled.numerator // scaled.denominator, half_up(scaled)):
            if n >= floor:
                forms.add("%de%d" % (n, k))
    return forms


def tested_forms(value, precision):
    """X25: a number of precision 10^k is tested as f:<round(v / 10^k)>e<k>; below a unit, k is 0, and the value is
    tested truncated as well as rounded (G23, R58), so 412,870.50 meets 412,870 as X25's tolerance says it does."""
    k, unit = 0, Fraction(precision)
    while unit >= 10 and k < 9:
        unit, k = unit / 10, k + 1
    scaled = Fraction(value) / 10 ** k
    ns = [half_up(scaled)] + ([scaled.numerator // scaled.denominator] if unit < 1 else [])
    return ["%de%d" % (n, k) for n in sorted(set(ns)) if n >= 1]


def exclusion_top(value):
    """G22 (R57): the largest k at which an exclusion figure's form still holds its first two significant digits, or
    its one for a figure written with one (70,000), so a coarse round number never stands for it; k = 0 always."""
    whole = abs(Fraction(value).numerator // Fraction(value).denominator)
    return max(0, len(str(whole)) - min(2, significant(value))) if whole else 0


def significant(value):
    """The significant digits of an exact value: 318,460 has five, 65,000 two."""
    value, steps = Fraction(value), 0
    while value.denominator != 1 and steps < 12:
        value, steps = value * 10, steps + 1
    return len(str(abs(value.numerator // value.denominator)).strip("0"))


def text_numbers(folded, original):
    """(value, precision) of every number of a text that is not a percentage, digit chains read whole (X25)."""
    found = [(n.value, n.precision, n.start, n.end) for n in parse_numbers(folded, original) if not n.percent]
    text = folded.text
    for chain in digit_chains(text, date_spans(text)):
        if not chain_is_date(text, chain):
            found.append((Fraction(int("".join(text[s:e] for s, e in chain))), Fraction(1), chain[0][0],
                          chain[-1][1]))
    return found


def vocabulary(text):
    """The normalised words of a long text; ASCII lines with no backtick are lower-cased directly, which is what
    fold() does."""
    found = set()
    for line in text.split("\n"):
        folded = line.lower() if line.isascii() and "`" not in line else fold_text(line)
        for match in TOKEN.finditer(folded):
            word = POSSESSIVE.sub("", match.group()) if len(match.group()) > 2 else match.group()
            word = word.replace("'", "").replace("’", "")
            if word:
                found.add(word)
    return found


def wall_stop(run):
    """X26 step 6 with Z12: the stop list of the harvest, the phonetic keys its words hold, and X26's own small
    list (G04: the days and months, the product words, the titles and acronyms and the plugin's shipped rows)."""
    if run.stop is None:
        rows = run.lists.rows if run.lists is not None else load_shipped(run)
        small = set(STOP_WORDS | PRODUCT_WORDS | CALENDAR_WORDS) | plugin_words(rows)
        # G01: the shared/ words come from the reviewed SHARED_WORDS region, never from the live folder.
        words = small | SHARED_WORDS
        keys = {word_key(w) for w in words | COMMON_WORDS} - {""}
        run.stop = (frozenset(words), frozenset(keys), frozenset(small))
    return run.stop


def shared_vocabulary(base=None):
    """G01: the words SHARED_WORDS should hold for the shared/ folder as it is now (its .md and .txt files, less the
    common words and the words with no letter). Used by the test that keeps the region equal to the shipped folder,
    and to regenerate the region after a reviewed change; the lint itself never calls it."""
    base = Path(base) if base is not None else PLUGIN / "shared"
    words = set()
    for path in sorted(base.iterdir()):
        if path.is_file() and path.suffix.lower() in (".md", ".txt"):
            words |= vocabulary(read_bytes(path).decode("utf-8-sig").replace("\r\n", "\n"))
    return {w for w in words if w not in COMMON_WORDS and any(c.isalpha() for c in w)}


def shared_phrases(base=None):
    """G04: the phrases SHARED_PHRASES should hold for the shared/ folder as it is now: each capitalised run of two
    to four words the harvest cuts from its .md and .txt files whose every word is made of letters and is a stop
    word (X26's small list, the rows of the folder's leak-terms.txt, or the folder's own words). A39 (R76): or a
    common word, when at least one word of the run is a stop word, so a phrase the plugin writes such as monday's
    Quotes & Invoices is no client's name either; a run of common words alone is never one. Like
    shared_vocabulary(), it serves the test and a reviewed regeneration; the lint itself never calls it."""
    base = Path(base) if base is not None else PLUGIN / "shared"
    rows = parse_list(read_bytes(base / "leak-terms.txt").decode("utf-8-sig"), SHIPPED_NAME, local=False)
    stop = set(STOP_WORDS | PRODUCT_WORDS | CALENDAR_WORDS) | plugin_words(rows) | shared_vocabulary(base)
    found = set()
    for path in sorted(base.iterdir()):
        if path.is_file() and path.suffix.lower() in (".md", ".txt"):
            text = read_bytes(path).decode("utf-8-sig").replace("\r\n", "\n")
            for words in harvest(text, frozenset(), frozenset(), phrases=frozenset()):
                if len(words) > 1 and all(w.isalpha() and (w in stop or w in COMMON_WORDS) for w in words) and \
                        any(w in stop for w in words):
                    found.add(" ".join(words))
    return found


def kept(words, stop, small, initials=False, phrases=SHARED_PHRASES):
    """X26 steps 5 and 6: a candidate kept for the digest, as its words with trailing legal suffixes dropped. G04: a
    run of two or more words is dropped only as a phrase the plugin writes or when every word is in X26's own small
    list; stop, which holds the shared/ words of Z12, filters single words only. G16 (R47): a single word is also
    dropped when it is a plural or inflected form of a stop word (thursdays with thursday), and G18 (R50) when its
    plural is one (requirement with requirements), since the checked side reads a plural as its singular (R43)."""
    words = list(words)
    while len(words) > 1 and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    if len(words) > 1:
        return None if " ".join(words) in phrases or all(w in small for w in words) else tuple(words)
    word = words[0] if words else ""
    if not word or word.isdigit() or word in LEGAL_SUFFIXES or word in COMMON_WORDS or word in stop or \
            any(stem in stop for stem in inflection_stems(word)) or any(form in stop for form in plural_forms(word)):
        return None
    return (word,) if len(word) >= 3 or (len(word) == 2 and initials) else None


def edge_word(token):
    """A39 (R76): a function word at a run's edge, unless it is written in capitals as an acronym (US, IT, OR)."""
    return token.word in FUNCTION_WORDS and not (token.upper and len(token.word) > 1)


def harvest(text, stop, small, alt=False, phrases=SHARED_PHRASES, entry=False):
    """X26 steps 2 to 4 over one D text: the capitalised runs and their sub-runs, the acronyms and the parts of
    every e-mail address, each kept by the filters of steps 5 and 6 (with alt, G02's second reading). With `entry`
    (an index entry's harvest, A39 R76), a run of two or more words that starts or ends with a function word is not
    a candidate; its sub-run without that word still is."""
    folded = fold(text, alt=alt)
    tokens, gaps = wall_cut(text, folded)
    found, k = set(), 0
    while k < len(tokens):
        if not tokens[k].cap:
            k += 1
            continue
        run, m = [k], k
        while True:
            if m + 1 < len(tokens) and HARVEST_GAP.fullmatch(gaps[m]) and tokens[m + 1].cap:
                run.append(m + 1)
                m += 1
            elif m + 2 < len(tokens) and tokens[m + 1].word in WALL_JOINERS and not tokens[m + 1].cap and \
                    HARVEST_GAP.fullmatch(gaps[m]) and HARVEST_GAP.fullmatch(gaps[m + 1]) and tokens[m + 2].cap:
                run += [m + 1, m + 2]
                m += 2
            else:
                break
        for a in range(len(run)):
            for b in range(a + 1, min(len(run), a + 4) + 1):
                first, last = tokens[run[a]], tokens[run[b - 1]]
                if entry and b - a > 1 and (edge_word(first) or edge_word(last)):
                    continue
                if first.cap and last.cap:
                    candidate = kept([tokens[x].word for x in run[a:b]], stop, small, b - a == 1 and first.upper,
                                     phrases)
                    if candidate:
                        found.add(candidate)
        k = m + 1
    for match in EMAIL.finditer(folded.text):
        local, _, domain = match.group().partition("@")
        parts = [p for p in re.split(r"[._%+-]+", local) if p]
        pieces = [[p] for p in parts] + ([parts, ["".join(parts)]] if len(parts) > 1 else [])
        for label in domain.split(".")[:-1]:
            words = words_of(label)
            if words and sum(c.isalpha() for c in label) >= 3:
                pieces += [words] + ([["".join(words)]] if len(words) > 1 else [])
        for piece in pieces:
            candidate = kept(piece, stop, small, phrases=phrases)
            if candidate:
                found.add(candidate)
    return found


def generic(words, stop):
    """A39 (R76): a harvested candidate that names nothing, so an index entry does not publish it: a key or a code
    (CODE_WORD), or a run that holds one; a single word of EVERYDAY_WORDS, or its plural; or a run whose every word
    is an everyday one (a common word, a stop or shared/ word, a word of EVERYDAY_WORDS, a joiner, or a plural or
    inflected form of one) and that holds a title, an acronym, a day or a month of X26 step 6 (GENERIC_WORDS:
    Account ID, Try the CRM). The product words and the shipped rows' words are not among them, since firms name
    themselves with work, service or management and a method row holds everyday words (store); a run of common or
    shared/ words alone, such as Blue Harbour, Signal Path or Cold Store, stays a name (G04). Every run's sub-runs
    are candidates of their own, so a name inside such a run stays published."""
    if any(CODE_WORD.fullmatch(word) for word in words):
        return True

    def everyday(word):
        return word in COMMON_WORDS or word in stop or word in EVERYDAY_WORDS or word in WALL_JOINERS or \
            any(stem in COMMON_WORDS or stem in stop or stem in EVERYDAY_WORDS for stem in inflection_stems(word))

    if len(words) == 1:
        return words[0] in EVERYDAY_WORDS or any(stem in EVERYDAY_WORDS for stem in plural_stems(words[0]))
    return any(word in GENERIC_WORDS for word in words) and all(everyday(word) for word in words)


def name_digests(candidates, vocabulary_keys):
    """(names, phonetic) of kept candidates (X26 steps 7 and 8; Z13 for the phonetic key of a single word)."""
    names, phonetic = set(), set()
    for words in candidates:
        names.add(digest("n:", " ".join(words)))
        if len(words) > 1:
            names.add(digest("n:", "".join(words)))
        for key in wall_keys(words, joined=True):
            if len(words) > 1 or key not in vocabulary_keys:
                phonetic.add(digest("p:", key))
    return names, phonetic


def spaced_and_fused(term):
    """The spaced and fused forms of a term, with and without trailing legal suffixes (X28 steps 6 and 7), in both
    readings of G02's letters."""
    forms = set()
    for alt in ((False, True) if has_alt(term) else (False,)):
        words = words_of(term, alt)
        while words:
            forms.update((" ".join(words), "".join(words)))
            if len(words) < 2 or words[-1] not in LEGAL_SUFFIXES:
                break
            words = words[:-1]
    return forms


def term_windows(term, small, phrases=SHARED_PHRASES):
    """G05: the spaced and fused forms of every window of two to four words of an exclusion term longer than four
    words, in both readings of G02's letters, since the cut of wall/1 makes no run longer than four (X27). A window
    whose every word is a common word or one of X26's own small list, or that is a phrase the plugin writes, is
    not published."""
    forms = set()
    for alt in ((False, True) if has_alt(term) else (False,)):
        words = words_of(term, alt)
        if len(words) <= 4:
            continue
        for i in range(len(words) - 1):
            for j in range(i + 2, min(len(words), i + 4) + 1):
                window = words[i:j]
                if " ".join(window) in phrases or all(w in COMMON_WORDS or w in small for w in window):
                    continue
                forms.update((" ".join(window), "".join(window)))
    return forms


def d_text(rel, text):
    """X11's D column: a record file's text that feeds the names, or None."""
    kind = kind_of(rel)
    if kind == "skip":
        return None
    if kind == "blueprint":
        lines = text.split("\n")
        client = blueprint_client_lines(lines)
        text = "\n".join("" if i in client else line for i, line in enumerate(lines))
    return blank_marks(text)


REFERENCED_ORIGIN = "pre-existing-referenced"  # the ledger's origin for a row that exists and is never written


def referenced_workspaces(run):
    """A36 (R71): the names of the workspaces this record's ledger holds as referenced rows (an `objects` row of a
    strand's solution/build.json with `type` workspace and `origin` pre-existing-referenced), when CLIENT.md's
    build_target is own-account: the test workspaces the user named for development builds, never a client's. The
    rule reads the ledger, so it holds for any name the user gives. A ledger the lint cannot read gives no name, so
    every name stays published (fail-safe)."""
    try:
        meta = mc.front_matter(record_texts(run).get("CLIENT.md") or "", "CLIENT.md")
    except mc.FrontMatterError:
        return []
    if (meta.get("build_target") or "").strip() != "own-account":
        return []
    names = set()
    for folder in strand_folders(run):
        path = folder / "solution" / "build.json"
        try:
            data = strict_json(run.text(path, run.name(path))) if path.is_file() else None
        except (mc.CannotRun, RepeatedKey, ValueError):
            continue
        objects = data.get("objects") if isinstance(data, dict) else None
        for row in (objects.values() if isinstance(objects, dict) else ()):
            if isinstance(row, dict) and row.get("type") == "workspace" and row.get("origin") == REFERENCED_ORIGIN \
                    and isinstance(row.get("name"), str) and words_of(row["name"]):
                names.add(row["name"])
    return sorted(names)


def unnamed(text, names):
    """A36 (R71): the text with every occurrence of the names, in any letter case and with any spacing or marks
    between their words, replaced by a line break, so the harvest never reads them or their words as a run. The same
    words written anywhere else in the record are harvested as before."""
    for name in names:
        words = [re.escape(word) for word in TOKEN.findall(name)]
        text = re.sub(r"(?<![^\W_])%s(?![^\W_])" % r"[\W_]+".join(words), "\n", text, flags=re.IGNORECASE)
    return text


def build_entry(run, client, slug, former=()):
    """This record's clients-index/1 lists (X02, X25, X26): names, phonetic keys, exclusion terms and figures, and the
    sorted single words the names publish (G16, for index's output). The client's former names (R40) are published
    in X26 step 1's forms beside its name, so a renamed client stays walled under its old names for every other
    record. A36 (R71): the names of the test workspaces the record's ledger holds as referenced are not harvested.
    A39 (R76): nor are the runs that start or end with a function word, and generic() drops the codes, the everyday
    words and the short generic phrases, so the entry publishes names."""
    stop, vocabulary_keys, small = wall_stop(run)
    candidates, lower = set(), set()
    referenced = referenced_workspaces(run)
    for rel, text in record_texts(run).items():
        piece = d_text(rel, text)
        if piece and referenced:
            piece = unnamed(piece, referenced)
        if piece:
            candidates |= harvest(piece, stop, small, entry=True)
            lower |= lower_words(piece)
            if has_alt(piece):
                candidates |= harvest(piece, stop, small, alt=True, entry=True)
                lower |= lower_words(piece, alt=True)
    # G16 (R47): a harvested single word is published only when the record never writes it in lower case as prose,
    # since a real name is capitalised every time; a run keeps it, and X26 step 1's forms below are always kept.
    # A39 (R76): nor is a candidate that names nothing (generic): a code, an everyday word, a short generic phrase.
    candidates = {words for words in candidates if (len(words) > 1 or words[0] not in lower) and
                  not generic(words, stop)}
    named = [client] + list(former)
    for value, alt in [(slug, False)] + [(v, False) for v in named] + [(v, True) for v in named if has_alt(v or "")]:
        forms = [w for w in [words_of(value, alt)] if w]  # X26 step 1: always included
        while forms and len(forms[-1]) > 1 and forms[-1][-1] in LEGAL_SUFFIXES:
            forms.append(forms[-1][:-1])
        candidates.update(tuple(words) for words in forms)
    names, phonetic = name_digests(candidates, vocabulary_keys)
    terms, figures = set(), set()
    for pattern in run.exclusions.patterns:
        forms = spaced_and_fused(pattern.term) | term_windows(pattern.term, small)  # G05: a long term's windows
        terms.update(digest("n:", form) for form in forms)
    for value, _, _, _ in run.sets.cost:
        if value >= 1000 and significant(value) >= 3:
            figures.update(digest("f:", form) for form in figure_forms(value, 100))
    for value, _, _, _ in run.exclusions.figures:  # G22 (R57): two significant digits, or the figure's own one
        figures.update(digest("f:", form) for form in figure_forms(value, 1, exclusion_top(value)))
    lists = {"names": sorted(names), "phonetic": sorted(phonetic), "terms": sorted(terms), "figures": sorted(figures)}
    return lists, sorted({words[0] for words in candidates if len(words) == 1})


def index_problem(field, problem, expected="a clients-index/1 file written by leak_lint.py index"):
    return cannot(INDEX_NAME, field, problem, expected)


def read_index(run, locked=False):
    """(entries, the text as read or None): the index read with utf-8-sig and checked against clients-index/1;
    an absent index reads as empty (L48); a newer, other or malformed one is exit 3 (L47, L203, X02). A reader
    holds the home mutex when it already exists, and never creates it (X29)."""
    path = run.home / "clients-index.json"
    unread = index_problem(WHOLE, "the home cannot be read, so the index or its mutex cannot be looked at",
                           "a home readable by the user who runs the lint, then run this again")
    try:  # G08, A24: a home that cannot be looked into is exit 3 on 3.9 and 3.14 alike, never an absent index
        kind = path_kind(path)
    except OSError:
        raise unread
    if kind is None:
        run.absent(INDEX_NAME)
        return {}, None
    if kind != "file":
        raise index_problem(WHOLE, "the index is not a file")
    try:
        held = not locked and path_kind(run.home / ".work" / "record.mutex") == "file"
    except OSError:
        raise unread
    if held:
        with mc.record_mutex(run.home):
            return read_index(run, locked=True)
    text = run.text(path, INDEX_NAME)
    data = json_value(text, INDEX_NAME, "each key written once in its object, as leak_lint.py index writes it; "
                      "restore the last copy from <home>/local/backup/ if the file was edited by hand")
    if not isinstance(data, dict):
        raise index_problem(WHOLE, "the index is not a JSON object")
    schema = data.get(INDEX_FIELDS[1])
    if schema != INDEX_FIELDS[0]:
        name, _, number = str(schema).partition("/")
        newer = name == "clients-index" and number.isdigit() and int(number) > 1
        raise index_problem(INDEX_FIELDS[1], "schema %s is newer than this lint's" % schema if newer else
                            "schema %r is not clients-index/1" % (schema,), INDEX_FIELDS[0])
    for field, value in ((INDEX_FIELDS[2], INDEX_FORMS[0]), (INDEX_FIELDS[3], INDEX_FORMS[1])):
        if data.get(field) != value:
            raise index_problem(field, "%s is %r, which this lint does not read" % (field, data.get(field)), value)
    if set(data) != set(INDEX_FIELDS[1:5]) or not isinstance(data[INDEX_FIELDS[4]], dict):
        raise index_problem(WHOLE, "the index does not hold exactly schema, hash, normalisation and an entries "
                            "object")
    entries = data[INDEX_FIELDS[4]]
    for key, entry in entries.items():
        field = "entries.%s" % key
        if not HEX32.fullmatch(key) or not isinstance(entry, dict) or set(entry) != set(INDEX_FIELDS[5:10]):
            raise index_problem(field, "an entry that is not a 32-hex key over updated and the four lists")
        if not isinstance(entry[INDEX_FIELDS[5]], str) or not UTC_STAMP.fullmatch(entry[INDEX_FIELDS[5]]):
            raise index_problem(field + ".updated", "not a UTC time")
        try:  # R44 compares the stamp with file times, so it must be a real moment
            mc.parse_utc(entry[INDEX_FIELDS[5]])
        except ValueError:
            raise index_problem(field + ".updated", "not a UTC time")
        for name in LIST_FIELDS:
            values = entry[name]
            if not isinstance(values, list) or not all(isinstance(v, str) and HEX32.fullmatch(v) for v in values):
                raise index_problem("%s.%s" % (field, name), "not a list of 32-hex digests")
    return entries, text


def index_text(entries):
    return mc.json_text({INDEX_FIELDS[1]: INDEX_FIELDS[0], INDEX_FIELDS[2]: INDEX_FORMS[0],
                         INDEX_FIELDS[3]: INDEX_FORMS[1], INDEX_FIELDS[4]: {k: entries[k] for k in sorted(entries)}})


EXCLUSIONS_FILE = re.compile(r"strands/[^/]+/solution/exclusions\.md")
ENTRY_SLACK = 2  # R44: seconds past the end of an entry's stamped second before a newer file makes it older


def feeds_entry(rel):
    """R44: whether a record file's text can reach the record's index entry: every file d_text and the sets read
    (X11's D and F columns), and every strand's exclusions.md, whose rows are the entry's terms. The allowlist and
    the live map feed O only (Y01), so they leave the entry as current as it was."""
    return kind_of(rel) != "skip" or bool(EXCLUSIONS_FILE.fullmatch(rel))


def newest_change(found, failed):
    """R44: the latest modification or status-change time, in seconds, of the files of record_walk's result that
    feed the entry, by os.stat alone; no file is opened (X30). The status-change time also moves when a file is
    copied or moved in with an older modification time. A file gone since the walk is passed over, since a removal
    adds nothing; any other failure goes to failed(exc). 0 when there is no such file."""
    newest = 0.0
    for rel in sorted(found):
        if not feeds_entry(rel):
            continue
        try:
            info = os.stat(str(found[rel]))
        except FileNotFoundError:
            continue
        except OSError as exc:
            failed(exc)
        newest = max(newest, info.st_mtime, info.st_ctime)
    return newest


def entry_is_older(entry, newest):
    """R44: whether an index entry is older than the newest change of its record's files. The stamp keeps whole
    seconds, so a file changed later in the same second, or within ENTRY_SLACK seconds after it, is not counted
    against the entry: coarse file times and a small disagreement between the file system's clock and this one."""
    return newest >= mc.parse_utc(entry[INDEX_FIELDS[5]]).timestamp() + 1 + ENTRY_SLACK


def other_record_newest(path):
    """R44: newest_change for another client record under the home. A folder in it that cannot be listed or
    looked at, or a link that leads out of it, is exit 3 naming no folder (X30): the wall cannot tell whether that
    record's entry is current, and the record's own index run names what stops it there."""

    def stop(*_):
        raise cannot(INDEX_NAME, INDEX_FIELDS[4], "a client record under the home cannot be looked through, so the "
                     "wall cannot tell whether its index entry is current", "every client record under the home "
                     "readable by the user who runs the lint, with no link that leads out of it; leak_lint.py index "
                     "run from a record names what stops it there; then run this again")

    return newest_change(record_walk(path, stop, stop), stop)


def path_kind(path):
    """G08, A24: "dir", "file", "other" or None (no such path) for a home path, by os.stat, which follows a link
    as pathlib does. Any other failure, such as a folder that cannot be searched, raises OSError: pathlib's is_dir,
    is_file and exists raise it under 3.9 and answer False under 3.14, so each caller turns it into its own exit 3
    and both interpreters stop alike (X30, L205)."""
    try:
        mode = os.stat(str(path)).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    return "dir" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode) else "other"


def twin_folder(run):
    """G07, G15: this record's place under the home, checked before the wall or the index is built from it. First,
    the record's resolved parent must be <home>/clients or <home>/archive, both sides resolved so that a home reached
    through a link still matches (A§5.3): a record under no root of this home (another MMB_HOME, a moved home, a
    record copied out) cannot see its neighbours on this home's wall, and its entry would land in an index that holds
    no folder of it (X30). Then a folder of this record's name under the home's other root (archive/ for a record in
    clients/, and the other way round) is another client with the same slug, which Z18 item 4 would take for this
    record. Exit 3, naming the root only (X30). Two paths are looked at; nothing is listed or opened, and a path that
    cannot be looked at counts as a twin."""
    here = os.path.normcase(str(run.root.parent))
    roots = [f for f in ("clients", "archive") if os.path.normcase(os.path.realpath(str(run.home / f))) == here]
    if not roots:
        raise cannot("CLIENT.md", "record", "this record is not under <home>/clients/ or <home>/archive/ of the home "
                     "in use, so the wall cannot see the client records beside it", "a record at "
                     "<home>/clients/<slug>/ or <home>/archive/<slug>/: point MMB_HOME at the home that holds this "
                     "record, or move the record into that home's clients/, then run this again")
    for folder in ("clients", "archive"):
        if folder in roots:  # the record's own root: the path is this record
            continue
        twin = run.home / folder / run.root.name
        try:
            if path_kind(twin) != "dir" or twin.resolve() == run.root:
                continue
        except OSError:
            pass
        raise cannot("<home>/%s/" % folder, WHOLE, "a folder with this record's name is also under <home>/%s/, so "
                     "the wall cannot tell this record from that client" % folder,
                     "one folder per slug across <home>/clients/ and <home>/archive/: give one of the two records "
                     "another slug, then run this again")


def name_key(name):
    """G07: the digest every entry holds for its CLIENT.md name (X26 step 1), or None for a record with no name."""
    words = words_of(name or "")
    return digest("n:", " ".join(words)) if words else None


def holds_own_name(entry, names):
    """G07, R40: whether an index entry holds the digest of this record's CLIENT.md name or of any of its former
    names, the one test that tells this client's own entry from another client's on the same slug."""
    return bool(({name_key(name) for name in names} - {None}) & set(entry["names"]))


def entry_is_damaged(entry, folder=None):
    """G14, R45: whether an index entry cannot be one index wrote. X26 step 1 always publishes the slug, which is the
    folder's name (X30), so every entry holds at least that name's spaced digest: an entry with no names, or, where
    its folder is known, without that digest, was emptied or only partly restored."""
    return not entry["names"] or (folder is not None and name_key(folder) not in entry["names"])


def home_folders(run):
    """[(folder name, holds CLIENT.md, path)] of the folders directly under <home>/clients/ and <home>/archive/, this
    record's own and any folder of its name left out (X21, X30); twin_folder has already stopped a run where a
    folder of its name is another record (G07). Only the listing is read."""
    found = []
    for folder in ("clients", "archive"):
        base = run.home / folder
        try:
            entries = sorted(base.iterdir()) if path_kind(base) == "dir" else []
        except OSError as exc:
            raise cannot("<home>/%s/" % folder, WHOLE, "cannot list the folder: %s" % exc, "a readable home")
        for entry in entries:
            try:
                if path_kind(entry) != "dir":
                    continue
                if run.record:
                    try:
                        same = entry.resolve() == run.root
                    except OSError:
                        same = False
                    if same or entry.name == run.root.name:
                        continue
                found.append((entry.name, path_kind(entry / "CLIENT.md") == "file", entry))
            except OSError:
                # G08, X30: a folder that cannot be looked into may be a client record; the error names no folder,
                # because its name would carry that client's slug into this session.
                raise cannot("<home>/%s/" % folder, INDEX_FIELDS[4], "a folder under the home cannot be read, so "
                             "the wall cannot tell whether it is a client record", "every folder directly under "
                             "<home>/clients/ and <home>/archive/ readable by the user who runs the lint, then run "
                             "this again")
    return found


class Own:
    """O, this record's own set (X27): every wall/1 candidate ("n"), phonetic key ("p") and figure form ("f") of
    its O sources, in plaintext in memory only, with the files that hold each, so a checked record file never
    makes its own words this record's (Z15)."""

    def __init__(self):
        self.count, self.files, self.skip = {}, {}, {}

    def left_out(self, file):
        """The files O leaves out while `file` is checked (Z15): the file itself and, for a blueprint, every
        blueprint file of its strand, because record.py freeze copies its bytes into versions/ (G09)."""
        if file not in self.skip:
            strand = file.split("/")[:2]
            self.skip[file] = {file} | ({rel for rel in self.files if kind_of(rel) == "blueprint" and
                                         rel.split("/")[:2] == strand} if kind_of(file) == "blueprint" else set())
        return self.skip[file]

    def add(self, rel, text):
        folded = fold(text)
        mine = set()
        for reading in [folded] + ([fold(text, alt=True)] if has_alt(text) else []):  # G02: both readings
            tokens, gaps = wall_cut(text, reading)
            for i, j, form, fused in wall_candidates(tokens, gaps):
                mine.add(("n", form))
                if not fused:
                    mine.update(("p", key) for key in wall_keys([t.word for t in tokens[i:j]]))
        for value, _, _, _ in text_numbers(folded, text):
            mine.update(("f", form) for form in figure_forms(value, 1))
        self.files[rel] = mine
        for item in mine:
            self.count[item] = self.count.get(item, 0) + 1

    def has(self, kind, value, file):
        item = (kind, value)
        count = self.count.get(item, 0)
        if count:
            count -= sum(1 for rel in self.left_out(file) if item in self.files.get(rel, ()))
        return count > 0


class Wall:
    """The other records' digests, the other folders' slugs, and O (absent under terms, which has no record)."""

    def __init__(self):
        self.names, self.terms, self.phonetic, self.figures = set(), set(), set(), set()
        self.slugs, self.slug_keys, self.own = set(), set(), None
        self.entries = self.folders = 0
        self.ordinary = COMMON_WORDS

    def name_class(self, form, file):
        if self.own is not None and self.own.has("n", form, file):
            return None
        hashed = digest("n:", form)
        if hashed in self.names:
            return "name"
        if hashed in self.terms:
            return "term"
        return "slug" if form in self.slugs else None

    def key_class(self, key, file):
        if self.own is not None and self.own.has("p", key, file):
            return None
        if digest("p:", key) in self.phonetic:
            return "name"
        return "slug" if key in self.slug_keys else None

    def gated(self, words):
        """Z13 item 2's gate: a word outside the ordinary words, and seven letters or more in all."""
        return not all(w in self.ordinary for w in words) and sum(len(letters(w)) for w in words) >= 7

    def shape_class(self, form, words, fused, split, initial, file):
        """G12 (R43), the checked side only: an initial written apart from its capitalised word (O Rourke, O’ Rourke)
        looked up fused to it, and each word with a plural ending removed (plural_stems), spaced or fused as the
        candidate is and, for a run of two or three words with only white space between them that passes Z13 item 2's
        gate, also joined (G11). Nothing is looked up when O holds the candidate itself."""
        shapes = [[words[0] + words[1]] + words[2:]] if initial else []
        for base in [words] + shapes:
            for k, word in enumerate(base):
                shapes.extend(base[:k] + [stem] + base[k + 1:] for stem in plural_stems(word))
        if not shapes or (self.own is not None and self.own.has("n", form, file)):
            return None
        for shape in shapes:
            cls = self.name_class(("" if fused else " ").join(shape), file)
            if cls is None and split and len(shape) > 1 and self.gated(shape):
                cls = self.name_class("".join(shape), file)
            if cls:
                return cls
        return None

    def initials(self, tokens, gaps, file):
        """G25 (R60), the checked side only: single capital letters with spaces, tabs or a full stop between them
        (T F M, T  F  M, T. F. M.) are initials, and each run of two to six of them, the lengths X26 step 3 publishes,
        is looked up fused, unless O holds the run spaced. Capitals only, so a lone a or I in prose never joins."""
        found, i = [], 0
        while i < len(tokens):
            j = i
            while j < len(tokens) and len(tokens[j].word) == 1 and tokens[j].word.isalpha() and tokens[j].upper and \
                    (j == i or INITIALS_GAP.fullmatch(gaps[j - 1])):
                j += 1
            for a in range(i, j):
                for b in range(a + 2, min(j, a + 6) + 1):
                    words = [t.word for t in tokens[a:b]]
                    if self.own is not None and self.own.has("n", " ".join(words), file):
                        continue
                    cls = self.name_class("".join(words), file)
                    if cls:
                        found.append((tokens[a].start, tokens[b - 1].end, cls))
            i = max(j, i + 1)
        return found

    def hits(self, check):
        unit, found = check.unit, []
        if unit.kind != "number":
            variants = [(check.vf, check.tokens)]
            if check.vfd is not None:
                variants.append((check.vfd, tokenise(check.text, check.vfd)))
            if has_alt(check.text):  # G02: the second reading of ø, æ and œ
                second = fold(check.text, alt=True)
                variants.append((second, tokenise(check.text, second)))
            for folded, tokens in variants:
                tokens, gaps = wall_cut(check.text, folded, tokens)
                for i, j, form, fused in wall_candidates(tokens, gaps):
                    cls = self.name_class(form, unit.file)
                    words = [t.word for t in tokens[i:j]]
                    split = not fused and 2 <= j - i <= 3 and not any(gap.strip() for gap in gaps[i:j - 1])
                    if cls is None and not fused and self.gated(words):  # Z13: what may sound like another's name
                        for key in sorted(wall_keys(words)):
                            cls = cls or self.key_class(key, unit.file)
                        # G11: under the same gate, a run of two or three words with only white space between them is
                        # also looked up joined, as another record's one-word name written split, unless O holds it.
                        if cls is None and split and not (self.own is not None and self.own.has("n", form, unit.file)):
                            cls = self.name_class("".join(words), unit.file)
                    if cls is None:
                        initial = not fused and j - i >= 2 and len(words[0]) == 1 and words[0].isalpha() and \
                            tokens[i + 1].cap and bool(INITIAL_GAP.fullmatch(gaps[i]))
                        cls = self.shape_class(form, words, fused, split, initial, unit.file)
                    if cls:
                        found.append((tokens[i].start, tokens[j - 1].end, cls))
                found.extend(self.initials(tokens, gaps, unit.file))
        if not unit.structural and self.figures:
            for folded in [check.vf] + ([check.vfd] if check.vfd is not None else []):
                for value, precision, start, end in text_numbers(folded, check.text):
                    if any(digest("f:", form) in self.figures and
                           (self.own is None or not self.own.has("f", form, unit.file))
                           for form in tested_forms(value, precision)):
                        found.append(folded.span(start, end) + ("figure",))
        found.sort(key=lambda h: (h[0], -h[1]))
        merged = []
        for start, end, cls in found:
            same = [m for m in merged if m[2] == cls and start < m[1] and m[0] < end]
            if same:
                index = merged.index(same[-1])
                merged[index] = (min(start, same[-1][0]), max(end, same[-1][1]), cls)
                continue
            merged.append((start, end, cls))
        return [("wall", cls, "block", start, end, WALL_PROBLEMS[cls], WALL_EXPECTED, None, {})
                for start, end, cls in merged]


def build_wall(run):
    """The wall for this run: the index read and checked, the coverage check of X30, the other entries' digests
    joined, the slugs of X21, and O built fresh from the record (X27)."""
    if run.record:
        twin_folder(run)
    entries, _ = read_index(run)
    folders = home_folders(run)
    missing = sum(1 for name, has_client, _ in folders if has_client and mc.slug_key(name) not in entries)
    if missing:
        raise cannot(INDEX_NAME, INDEX_FIELDS[4], "%d other client record%s under the home %s no index entry, so the "
                     "wall cannot see %s" % (missing, "" if missing == 1 else "s", "has" if missing == 1 else "have",
                                             "it" if missing == 1 else "them"),
                     "run leak_lint.py index from each of those records, then run this again")
    # G14, R45: an entry index cannot have written passes Z18 item 3's shape check but may wall less than its record
    # holds, so it fails closed as a malformed index does. The folder test needs the folder's name only, and the
    # error gives the count only (X30).
    keyed = {mc.slug_key(name): name for name, _, _ in folders}
    damaged = sum(1 for key, entry in entries.items() if entry_is_damaged(entry, keyed.get(key)))
    if damaged:
        raise cannot(INDEX_NAME, INDEX_FIELDS[4], "%d entr%s of the index %s damaged: leak_lint.py index always writes "
                     "a client's folder name among its names, and %s no names, or not that one, so the index was "
                     "emptied or only partly restored" % (damaged, "y" if damaged == 1 else "ies",
                                                          "is" if damaged == 1 else "are",
                                                          "it holds" if damaged == 1 else "they hold"),
                     "run leak_lint.py index from each client record under the home; if the index was restored from "
                     "a backup, restore the whole file from that backup, not part of it; then run this again")
    # G13, R44: an entry older than its record's files may lack what was added since, so it fails closed as an
    # absent one does (X30); only the count is given. This record's folder is not in folders, so its own entry is
    # never checked for its age.
    older = sum(1 for name, _, path in folders if mc.slug_key(name) in entries and
                entry_is_older(entries[mc.slug_key(name)], other_record_newest(path)))
    if older:
        raise cannot(INDEX_NAME, INDEX_FIELDS[4], "%d other client record%s under the home %s changed since %s last "
                     "index, so the wall may not see what was added to %s" % (
                         older, "" if older == 1 else "s", "has" if older == 1 else "have",
                         "its" if older == 1 else "their", "it" if older == 1 else "them"),
                     "run leak_lint.py index from each client record changed since its last index, then run this "
                     "again")
    wall = Wall()
    own_key = mc.slug_key(run.root.name) if run.record else None
    if own_key in entries:
        # G07: the entry under this record's key is its own only when it holds this record's CLIENT.md name or one
        # of its former names (R40); one left by another client of the same slug stays that client's wall (X29).
        meta = mc.front_matter(record_texts(run).get("CLIENT.md") or run.text(run.root / "CLIENT.md", "CLIENT.md"),
                               "CLIENT.md")
        if not holds_own_name(entries[own_key], [meta.get("name") or ""] + mc.former_names(meta.get("former_names"))):
            own_key = None
    for key, entry in entries.items():
        if key == own_key:
            continue
        wall.entries += 1
        wall.names.update(entry["names"])
        wall.phonetic.update(entry["phonetic"])
        wall.terms.update(entry["terms"])
        wall.figures.update(entry["figures"])
    wall.folders = len(folders)
    if wall.phonetic or folders:
        wall.ordinary = COMMON_WORDS | wall_stop(run)[0]
    if folders:
        stop, vocabulary_keys, small = wall_stop(run)
        for name, _, _ in folders:
            words = words_of(name)
            candidates = {tuple(words)} if words else set()
            for a in range(len(words)):
                for b in range(a + 1, min(len(words), a + 4) + 1):
                    candidate = kept(words[a:b], stop, small)
                    if candidate:
                        candidates.add(candidate)
            for candidate in candidates:
                wall.slugs.add(" ".join(candidate))
                if len(candidate) > 1:
                    wall.slugs.add("".join(candidate))
                wall.slug_keys |= {k for k in wall_keys(candidate, joined=True)
                                   if len(candidate) > 1 or k not in vocabulary_keys}
    if run.record and (wall.names or wall.terms or wall.phonetic or wall.figures or wall.slugs):
        wall.own = Own()  # with nothing to compare, O is not needed and not read
        for rel, text in record_texts(run).items():
            text = own_text(rel, text)
            if text is not None:
                wall.own.add(rel, text)
    return wall


def own_text(rel, text):
    """G17 (R51): the part of a record file that feeds O, or None. Only this client's own words make a word this
    record's: calls/, inputs/ and research/ whole, and CLIENT.md's name, former names and slug. The blueprint's
    client-facing lines stay O, since payloads copy them (X11, R37). The session's working files (log.md,
    meetings.md, the strand files, solution/ notes, CLIENT.md's body, the blueprint's other lines) feed the harvest
    and the sets as before, and never O, so a line written in a mix-up of two clients never clears the other
    client's name. The allowlist feeds no set (Y01)."""
    kind = kind_of(rel)
    if kind in ("input", "call", "transcript") or rel.split("/")[0] == "research":
        return text
    if rel == "CLIENT.md":
        try:
            meta = mc.front_matter(text, "CLIENT.md")
        except mc.FrontMatterError:  # index refuses such a record; here O only loses its names, which adds blocks
            return None
        names = [meta.get("name") or "", meta.get("slug") or ""] + mc.former_names(meta.get("former_names"))
        return "\n\n".join(names)  # a blank line between them, so no run crosses from one name to the next
    if kind == "blueprint":  # the other lines are blanked in place, so no candidate runs across them
        lines = text.split("\n")
        client = blueprint_client_lines(lines)
        return "\n".join(line if index in client else "" for index, line in enumerate(lines))
    return None


def wall_hits(run, check):
    """The wall's findings for one unit (X01, X27, X45); with no unit, the wall is only built, so its index and
    coverage checks run before any text is judged."""
    if run.wall is None:
        run.wall = build_wall(run)
    return [] if check is None else run.wall.hits(check)


def finding(run, unit, text, rule, cls, severity, start, end, problem, expected, source, extra):
    field, line, column = unit.where(start)
    found = {"file": unit.file, "field": field, "problem": problem, "expected": expected, "rule": rule, "class": cls,
             "severity": severity, "line": line, "column": column, "match": cut(text[start:end]), "source": source}
    if unit.part:
        found["part"] = unit.part
    found.update(extra)
    found["_start"], found["_end"] = start, end
    found["_order"] = (0, unit.seq, start, rule, cls or "", found["match"] or "")
    return found


CONTAINED = ("term", "exclusion", "seller-account", "internal-note", "credential", "paraphrase", "split-figure")


HTML_PIECE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)\b[^<>]*>|&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|"
                        r"[A-Za-z][A-Za-z0-9]{1,31});?")
HTML_BREAKS = frozenset("p br div li ul ol tr td th table thead tbody h1 h2 h3 h4 h5 h6 blockquote pre hr section "
                        "article header footer".split())


def html_copy(text):
    """F05 (X24, X28): (the text with every tag blanked and every entity decoded, each character's offset in the
    text), or None when the text holds no tag or entity. A block tag becomes a line break, any other tag a space."""
    if "<" not in text and "&" not in text:
        return None
    out, where, last, changed = [], [], 0, False
    for match in HTML_PIECE.finditer(text):
        if match.group(2):
            piece = "\n" if match.group(2).lower() in HTML_BREAKS else " "
        else:
            piece = html.unescape(match.group())
        if piece == match.group():
            continue
        out.append(text[last:match.start()])
        where.extend(range(last, match.start()))
        out.append(piece)
        where.extend([match.start()] * len(piece))
        last, changed = match.end(), True
    if not changed:
        return None
    out.append(text[last:])
    where.extend(range(last, len(text)))
    return "".join(out), where


def html_hits(run, unit, text, hits, rules=None):
    """The hits of the HTML-decoded copy of a unit's text that its plain copy did not find, mapped back (F05);
    `rules` narrows the rules run on the copy (G19), every rule of the unit's mode by default."""
    copy = html_copy(text)
    if copy is None:
        return []
    decoded, where = copy
    sub = Unit(unit.file, decoded, unit.seq, field=unit.field, part=unit.part, strand=unit.strand, mode=unit.mode,
               kind=unit.kind, structural=unit.structural, sample=unit.sample)
    sub.own, sub.raw_json = unit.own, unit.raw_json
    plain_spans = [(h[0], h[1], h[3], h[4]) for h in hits]
    found = []
    check = Check(run, sub)
    for rule, cls, severity, start, end, problem, expected, source, extra in \
            (rules(run, check) if rules else check.execute()):
        if end <= start:
            continue
        start, end = where[start], where[end - 1] + 1
        if any(r == rule and c == cls and s < end and start < e for r, c, s, e in plain_spans):
            continue
        found.append((rule, cls, severity, start, end, problem, expected, source, extra))
    return found


def check_unit(run, unit):
    """Every rule the unit's mode runs, on the text and on its HTML-decoded copy, the findings deduplicated, then
    the strand's allowlist applied."""
    check = Check(run, unit)
    hits = check.execute()
    hits += html_hits(run, unit, check.text, hits)
    findings, seen = [], set()
    for rule, cls, severity, start, end, problem, expected, source, extra in hits:
        key = (rule, cls, start, end)
        if key in seen or end <= start:
            continue
        seen.add(key)
        findings.append(finding(run, unit, check.text, rule, cls, severity, start, end, problem, expected, source,
                                extra))
    kept = []
    for f in findings:
        if f["rule"] in CONTAINED and any(
                g is not f and g["rule"] == f["rule"] and g["class"] == f["class"] and g["_start"] <= f["_start"] and
                f["_end"] <= g["_end"] and (g["_end"] - g["_start"]) > (f["_end"] - f["_start"]) for g in findings):
            continue
        kept.append(f)
    kept = apply_allowlist(run, unit, check.text, kept)
    for f in kept:
        if run.spans and f["severity"] == "block" and "_start" in f:
            start, end = unit.raw_span(f["_start"], f["_end"])
            f["span"] = {"start": start, "end": end}
        run.add(f)


def apply_allowlist(run, unit, text, findings):
    """X10, X39, Y06: a row of the strand's own allowlist with the user's ok clears a vocabulary term, a
    paraphrase cue or one of the three internal-use phrases (R62) to a caution; a row that meets anything else leaves
    the block and warns once per finding."""
    rows = load_allowlist(run, unit.strand)
    if not rows:
        return findings
    extra = []
    for f in findings:
        if f["severity"] != "block":
            continue
        target = normal_form(text[f["_start"]:f["_end"]])
        matched = [r for r in rows if r.normal and r.normal == target]
        if not matched:
            continue
        if f["rule"] in ("term", "paraphrase") and f["class"] in CLEARABLE or \
                f["rule"] == "internal-note" and target in CLEARABLE_NOTES:
            granted = [r for r in matched if r.ok]
            if granted:
                f["severity"], f["cleared_by"] = "caution", "%s line %d" % (granted[0].file, granted[0].line)
                f["problem"] += "; kept as the client's own word"
                f["expected"] = "nothing: the strand's allowlist keeps it, with the user's ok"
            continue
        what = "%s of class %s" % (f["rule"], f["class"]) if f["class"] else f["rule"]
        for row in matched:
            warn = record_warning(row.file, row.line, "this row names a %s finding in %s %s; this class is never "
                                  "cleared by an allowlist" % (what, f["file"], f["field"]),
                                  "the text changed; the row clears nothing here", "allowlist")
            warn["match"] = cut(row.term)
            extra.append(warn)
    return findings + extra


# Inputs: what a command checks, as units (X08, X22, X35, X38).

def inside_record(run, value, flag):
    """(record-relative POSIX name, resolved path) of a path the session hands, which must lie inside the record."""
    if os.path.isabs(value):
        path = Path(value)
    else:
        path = run.root.joinpath(*[p for p in value.replace("\\", "/").split("/") if p not in ("", ".")] or ["."])
    resolved = Path(os.path.realpath(str(path)))
    try:
        rel = resolved.relative_to(Path(os.path.realpath(str(run.root)))).as_posix()
    except ValueError:
        raise cannot(value.replace("\\", "/"), flag, "the path lies outside the record", "a path inside the record, "
                     "so every finding names a record-relative file")
    if not resolved.exists():
        raise cannot(rel, flag, "no such file or folder in the record", "a file the session wrote")
    return rel, resolved


def path_strand(rel):
    match = re.match(r"strands/(\d{3})-[^/]+(?:/|$)", rel)
    return match.group(1) if match else None


def scan_targets(run, paths, flag):
    """[(record-relative name, path)] in the order given, a folder's files in sorted POSIX path order (X35)."""
    if not paths:
        folders = []
        for folder in strand_folders(run):
            if flag and not folder.name.startswith(flag + "-"):
                continue
            for sub in (("drafts",), ("deliverables", "handoff")):
                candidate = folder.joinpath(*sub)
                if candidate.is_dir():
                    folders.append(run.name(candidate))
        paths = folders
    targets = []
    for value in paths:
        rel, path = inside_record(run, value, "path")
        if path.is_dir():
            found = []

            def failed(exc):
                raise cannot(rel, WHOLE, "cannot list the folder: %s" % exc, "a readable folder")

            # F09: a linked folder is walked when it lies inside the record, else exit 3 naming it (R09)
            for folder, _, files in walk_inside(path, run.root, failed, lambda link, _: target_of(run, link, True)):
                for name in files:
                    found.append(Path(folder) / name)
            for item in sorted(found, key=lambda p: Path(os.path.realpath(str(p))).as_posix()):
                if item.name.lower() in SYSTEM_FILES:
                    continue
                targets.append(target_of(run, item))
        else:
            targets.append(target_of(run, path))
    for rel, _, _ in targets:
        strand = path_strand(rel)
        if flag and strand and strand != flag:
            raise cannot(rel, "--strand", "the path is in strand %s, not %s" % (strand, flag),
                         "--strand left out, or the strand the path is in")
    return targets


def target_of(run, path, folder=False):
    resolved = Path(os.path.realpath(str(path)))
    try:
        rel = resolved.relative_to(Path(os.path.realpath(str(run.root)))).as_posix()
    except ValueError:
        raise cannot(Path(path).name, "path", "a %s in the folder resolves outside the record" %
                     ("linked folder" if folder else "file"), "files inside the record only")
    if folder:
        return rel
    if os.path.splitext(rel)[1].lower() not in SCAN_EXT:
        raise cannot(rel, WHOLE, "the lint cannot read this kind of file", "a file the lint can read (.md, .txt, "
                     ".docx, .json); move this one out of the folder or convert it")
    return rel, resolved, path_strand(rel)


def scan_mode(rel, text):
    if re.fullmatch(r"strands/\d{3}-[^/]+/SUMMARY\.md", rel):
        return "summary"
    if rel.lower().endswith(".md") and (rel.startswith("calls/") or
                                        (rel.startswith("inputs/") and is_snapshot(rel, text))):
        return "client-safe-block"
    return "full"


def file_units(run, rel, path, strand, seq):
    """(mode, units) of one scanned file."""
    ext = os.path.splitext(rel)[1].lower()
    if ext == ".docx":
        units = []
        for index, (part, lines, labels) in enumerate(docx_text(run, path, rel)):
            units.append(Unit(rel, "\n".join(lines), (seq, index), part=part, strand=strand, labels=labels))
        return "full", units
    if ext == ".json":
        data = json_value(decode(run.read(path, rel, PAYLOAD_LIMIT), rel)[0], rel, ONCE_PAYLOAD)
        return "full", payload_units(rel, data, strand, seq)
    text, raw = decode(run.read(path, rel), rel)
    mode = scan_mode(rel, text)
    if mode != "client-safe-block":
        return mode, [Unit(rel, text, (seq, 0), strand=strand, mode=mode, raw=raw)]
    lines = text.split("\n")
    inside_lines, problem = block_lines(lines, BLOCK_MARKS[0], BLOCK_MARKS[1])
    if problem:
        raise cannot(rel, "line %d" % problem[0], "the client-safe marks are not well formed: %s" % problem[1],
                     "an opening and a closing mark, each alone on its line, so the lint can tell what is client-safe")
    if not inside_lines and not any(line.strip() == BLOCK_MARKS[0] for line in lines):
        run.add(record_warning(rel, 1, "no client-safe block in this file", "the call summary or snapshot with its "
                               "marked client-safe block"))
        return mode, []
    kept = "\n".join(line if index in inside_lines else " " * len(line) for index, line in enumerate(lines))
    return mode, [Unit(rel, kept, (seq, 0), strand=strand, mode=mode, raw=raw)]


def child_place(place, key, parent):
    """A39 (R75, R77): where the value under `key` of the object `parent` sits, for the two values the rules read by
    their place: "values" (a column_values map, keyed by column id), "phone" (a phone column's value there),
    "phone-number" (the digits of a phone value written as {phone, countryShortName}), "settings" (a column's settings
    or defaults), "labels" (their label list) and "label-number" (a label's colour, index or position). None for any
    other value, so the rules read it as before."""
    folded = key.replace("_", "").lower()
    if place == "values":
        return "phone" if PHONE_COLUMN.fullmatch(key) else None
    if place == "phone":
        return "phone-number" if key == "phone" and phone_object(parent) else None
    if place == "labels":
        return "label-number" if folded in LABEL_NUMBER_KEYS else None
    if place == "settings" and folded in LABEL_LISTS:
        return "labels"
    if place in ("phone-number", "label-number"):
        return None
    return "values" if folded in COLUMN_VALUES else "settings" if folded in SETTINGS_KEYS else None


def phone_object(value):
    """A39 (R75): a phone column's value as monday takes it in JSON: the digits and a two-letter country code, and
    nothing else beside them."""
    return isinstance(value, dict) and set(value) == {"phone", "countryShortName"} and \
        isinstance(value["countryShortName"], str) and bool(COUNTRY_CODE.fullmatch(value["countryShortName"]))


def payload_units(file, data, strand, seq, sample=False):
    """X22, Y08: every string, every object key and every number at every depth, a string holding JSON walked as
    JSON as well; a digit-only value under a structural id key is marked structural, and so (A33, R66) is an object
    key made only of digits, as monday keys a widget's or a mirror's settings by board id. With `sample` (A33, R69:
    an item batch, whose values are all invented), every unit is marked sample. A39: a phone column's value in
    column_values, in the shapes monday takes, is marked phone (R75), and a label's colour, index or position in a
    column's settings is marked label (R77); child_place() tells the place, which a string holding JSON passes on to
    the JSON inside it. The walk is iterative."""
    units, stack, count = [], [("$", data, 1, False, None)], 0
    while stack:
        path, value, depth, structural, place = stack.pop()
        if depth > DEPTH_LIMIT:
            raise cannot(file, path, "the payload is nested deeper than %d levels" % DEPTH_LIMIT,
                         "a tool input of ordinary depth")
        count += 1
        if isinstance(value, dict):
            pushed = []
            for key, sub in value.items():
                key = str(key)
                sub_path = key_path(path, key)
                units.append(Unit(file, key, (seq, len(units)), field=sub_path + "<key>", strand=strand,
                                  kind="payload", structural=is_structural(key), sample=sample))
                if structural_key(key) and isinstance(sub, list):
                    for index, item in enumerate(sub):
                        pushed.append(("%s[%d]" % (sub_path, index), item, depth + 1, is_structural(item), None))
                    continue
                pushed.append((sub_path, sub, depth + 1, structural_key(key) and is_structural(sub),
                               child_place(place, key, value)))
            stack.extend(reversed(pushed))
        elif isinstance(value, list):  # A39 (R77): a label list's items are labels; no other place reaches a list
            inner = place if place == "labels" else None
            stack.extend(reversed([("%s[%d]" % (path, i), item, depth + 1, False, inner)
                                   for i, item in enumerate(value)]))
        elif isinstance(value, str):
            unit = Unit(file, value, (seq, len(units)), field=path, strand=strand, kind="payload",
                        structural=structural, sample=sample)
            unit.joins = not structural  # G19 (R53): a structural id is structure, as a key is
            unit.phone = place == "phone" and bool(PHONE_TEXT.fullmatch(value)) or \
                place == "phone-number" and bool(PHONE_DIGITS.fullmatch(value))
            unit.label = place == "label-number" and bool(DIGIT_RUN.fullmatch(value))
            units.append(unit)
            # G06: format characters dropped first, and a JSON string literal (a text column's value) parsed too.
            stripped = "".join(c for c in value if c not in IGNORABLE and unicodedata.category(c) != "Cf").strip()
            if stripped[:1] in ("{", "[", '"'):
                try:  # G20 (R54): a key written twice in JSON inside a string is exit 3, at the path through it
                    inner = strict_json(stripped, path + "<json>")
                except RepeatedKey as exc:
                    raise repeated(file, exc, ONCE_PAYLOAD)
                except ValueError:
                    inner = None
                if isinstance(inner, (dict, list)):
                    unit.raw_json = True  # F26: the walk checks every inner value, so the id rows skip the raw string
                    # A39 (R77): and a column's settings written as JSON warn on their numbers from the values walked
                    # inside, where a label's text still warns and its colour does not; the raw string stays quiet.
                    unit.label = place in ("settings", "labels")
                    stack.append((path + "<json>", inner, depth + 1, False, place))
                elif isinstance(inner, str):  # R34: its own unit; the raw string keeps every rule, the id rows too
                    stack.append((path + "<json>", inner, depth + 1, False, place))
                if isinstance(inner, (dict, list, str)):
                    unit.joins = False  # G19 (R53): the strings walked inside it join in its place
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            text = str(value) if isinstance(value, int) else repr(value)
            unit = Unit(file, text, (seq, len(units)), field=path, strand=strand, kind="number",
                        structural=structural, sample=sample)
            unit.label = place == "label-number" and isinstance(value, int)  # A39 (R77)
            units.append(unit)
    return units


def spanning_rules(run, check):
    """G19 (R53): the rules a text split over two payload strings can still meet: copied runs, quotes and the wall.
    The single-text rules stay with each string, so the joined text never reports them twice."""
    check.runs_and_quotes()
    return check.hits + wall_hits(run, check)


def check_joined(run, file, units, strand):
    """G19 (R53, A§:916, X22): one joined text per payload or scanned JSON file: every string that joins (no key, no
    number, no structural id, and a string holding JSON replaced by the strings walked inside it) in walk order,
    joined by single line breaks, under spanning_rules on the text and on its HTML-decoded copy. A hit inside one
    string is that string's own check's; a hit across strings is reported at the first one it touches, with `fields`
    naming every string it spans, unless a finding of its rule and class in one of those strings already overlaps it."""
    parts = [unit for unit in units if unit.joins]
    if len(parts) < 2:
        return
    starts, at = [], 0
    for unit in parts:
        starts.append(at)
        at += len(unit.text) + 1
    joined = Unit(file, "\n".join(unit.text for unit in parts), (parts[0].seq[0], len(units)), field="$",
                  strand=strand, kind="payload")
    check = Check(run, joined)
    hits = spanning_rules(run, check)
    hits += html_hits(run, joined, check.text, hits, spanning_rules)
    offsets = {unit.field: start for unit, start in zip(parts, starts)}
    found_before = [(f["rule"], f["class"], offsets[f["field"]] + f["_start"], offsets[f["field"]] + f["_end"])
                    for f in run.findings if f["file"] == file and f.get("field") in offsets and "_start" in f]
    findings, seen = [], set()
    for rule, cls, severity, start, end, problem, expected, source, extra in hits:
        first, last = bisect.bisect_right(starts, start) - 1, bisect.bisect_right(starts, end - 1) - 1
        if end <= start or first == last or (rule, cls, start, end) in seen or any(
                r == rule and c == cls and s < end and start < e for r, c, s, e in found_before):
            continue
        seen.add((rule, cls, start, end))
        extra = dict(extra, fields=[unit.field for unit in parts[first:last + 1]])
        f = finding(run, parts[first], check.text, rule, cls, severity, start, end, problem, expected, source, extra)
        f["_unit"] = first
        findings.append(f)
    for f in apply_allowlist(run, joined, check.text, findings):
        if "_unit" in f:  # back to the first string's own offsets, for the order and for --spans
            index = f.pop("_unit")
            unit, base = parts[index], starts[index]
            f["_start"], f["_end"] = f["_start"] - base, min(f["_end"] - base, len(unit.text))
            f["_order"] = (0, unit.seq, f["_start"]) + f["_order"][3:]
            if run.spans and f["severity"] == "block":
                start, end = unit.raw_span(f["_start"], f["_end"])
                f["span"] = {"start": start, "end": end}
        run.add(f)


def is_structural(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return isinstance(value, str) and bool(STRUCTURAL_VALUE.fullmatch(value))


def structural_key(key):
    """Y08, A33 (R66): whether a digit-only value under this key is a monday id: a key of the pinned list, or one
    that ID_KEY reads as naming an id."""
    return key in STRUCTURAL_ID_KEYS or bool(ID_KEY.fullmatch(key))


# The commands (X08). Each returns its exit code; the run carries what the envelope prints.

def prepare(run):
    load_lists(run)
    run.exclusions = load_exclusions(run)
    run.sets = build_sets(run)


def cmd_scan(run):
    run.locate()
    flag = run.args.strand
    if flag is not None:
        strand_folder(run, flag)
    targets = scan_targets(run, run.args.paths, flag)
    if not targets:  # F23 (A9.6, fail closed): a scan that judged nothing never reads as clean
        if not run.args.paths:  # R78: no path and no draft says so plainly, as the answer and not a fault of the lint
            folder = strand_folder(run, flag).name if flag else None
            raise cannot("strands/%s/drafts/" % folder if folder else "strands/", "path",
                         "no draft exists for strand %s: its drafts/ and deliverables/handoff/ hold no file" % flag
                         if folder else "no draft exists: no strand's drafts/ or deliverables/handoff/ holds a file",
                         "the path of the file to check, passed after scan (a file under the strand's drafts/)")
        raise cannot(run.args.paths[0].replace("\\", "/"), "path", "no draft or handoff file to check",
                     "the drafts/ or deliverables/handoff/ files of the strand, or the paths to check")
    prepare(run)
    modes, strands = [], set()
    for seq, (rel, path, strand) in enumerate(targets):
        mode, units = file_units(run, rel, path, strand, seq)
        modes.append(mode)
        strands.add(strand or flag)
        if mode in ("summary", "client-safe-block") and rel in run.inputs:
            run.inputs[rel]["mode"] = mode
        for unit in units:
            check_unit(run, unit)
        if os.path.splitext(rel)[1].lower() == ".json":  # G19 (R53): a scanned JSON file is walked as a payload is
            check_joined(run, rel, units, strand)
    run.mode = modes[0] if modes and len(set(modes)) == 1 else (None if modes else "full")
    run.strand = strands.pop() if len(strands) == 1 else (flag if not strands else None)
    return outcome(run)


def cmd_payload(run):
    run.locate()
    args = run.args
    strand_folder(run, args.strand)
    run.strand = args.strand
    rel, path = inside_record(run, args.file, "--file")
    if not path.is_file():
        raise cannot(rel, "--file", "the payload is not a file", "the tool input written as one JSON file")
    data = json_value(decode(run.read(path, rel, PAYLOAD_LIMIT), rel)[0], rel, ONCE_PAYLOAD)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    run.args_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    prepare(run)
    units = payload_units(rel, data, args.strand, 0, sample=args.kind == "item_batch")  # A33 (R69)
    wall_hits(run, None)
    for unit in units:
        check_unit(run, unit)
    check_joined(run, rel, units, args.strand)
    return outcome(run)


def cmd_blueprint(run):
    """X08, X09, X36: the blueprint's client-facing text (sections 1 to 15, the prompt blocks, the glossary) under
    every rule, the wall included, but the copied-run and quote rules, which A33 (R68) drops for the blueprint."""
    run.locate()
    folder = strand_folder(run, run.args.strand)
    run.strand, run.mode = run.args.strand, MODES[3]
    path = folder / "solution" / "blueprint.md"
    rel = run.name(path)
    if not path.is_file():
        raise cannot(rel, WHOLE, "the strand has no blueprint", "solution/blueprint.md, the blueprint drafted for "
                     "this strand")
    prepare(run)
    text, raw = decode(run.read(path, rel), rel)
    lines = text.split("\n")
    problem = section_problem(lines)
    if problem:
        raise cannot(rel, *problem)
    client = blueprint_client_lines(lines)
    glossary, problem = block_lines(lines, BLOCK_MARKS[2], BLOCK_MARKS[3])
    if problem:  # X09: malformed marks exempt nothing, and the text after each mark is checked to its heading
        run.add(record_warning(rel, problem[0], "glossary marks not well formed (%s); nothing in this file is exempt"
                               % problem[1], "an opening and a closing mark, each alone on its line"))
        client = set(client) | marked_lines(lines, BLOCK_MARKS[2:4])
    # R52: the title of each heading of sections 1 to 15 is client-facing too, checked with the section's text
    # under every rule and never as glossary text; its number and marks are blanked, so a hit sits on its line.
    titles = section_titles(lines)
    glossary = glossary - set(titles)
    checked = [i for i in sorted(set(client) | set(titles)) if i not in glossary]
    for mode, chosen in (("blueprint", set(checked)), ("glossary", glossary)):
        if chosen:
            kept_text = "\n".join(titles.get(i, line) if i in chosen else " " * len(line)
                                  for i, line in enumerate(lines))
            check_unit(run, Unit(rel, kept_text, (0, 0), strand=run.strand, mode=mode, raw=raw))
    return outcome(run)


def section_number(line):
    """X09, R49: the number a level-2 heading opens with (`## 4`, `## 4.`, `## 4)`, `## 4:`, `## 4 Title`), or None
    for any other line."""
    heading = HEADING.match(line)
    if not heading or len(heading.group(1)) != 2:
        return None
    number = SECTION_NUMBER.match(heading.group(2))
    return int(number.group(1)) if number else None


def section_titles(lines):
    """R52: {index: the line with only its title kept} for each level-2 heading numbered 1 to 15 whose title is not
    its section's own in the template (SECTION_TITLES). The title is the text after the number and its separator,
    before any closing hashes; the rest is blanked so positions stay."""
    titles = {}
    for index, line in enumerate(lines):
        number = section_number(line)
        if number in CLIENT_SECTIONS:
            heading = HEADING.match(line)
            start, end = heading.start(2) + SECTION_NUMBER.match(heading.group(2)).end(), heading.end(2)
            if words_of(line[start:end]) != words_of(SECTION_TITLES[number - 1]):
                titles[index] = " " * start + line[start:end] + " " * (len(line) - end)
    return titles


def section_problem(lines):
    """R49 (G18, X09, D19): None when level-2 headings numbered 1 to 15 are each found once and in order before
    section 16, and no other level-1 or level-2 heading sits among them; else the (field, problem, expected) of the
    stop. The text after section 16 is internal, under any heading. A blueprint without section 16 runs its
    sections to the end of the file, so every heading after section 15 counts as before section 16."""
    guide = ("write the sixteen section headings as blueprint-guide.md numbers them (## 4. Structure mapping), with "
             "every added item inside one of them as a level-3 subsection (### <item>), then run this again")
    numbers = [n for n in map(section_number, lines) if n in CLIENT_SECTIONS or n == 16]
    head = numbers[:numbers.index(16)] if 16 in numbers else numbers
    if head != list(CLIENT_SECTIONS) or len(numbers) - numbers.count(16) != len(CLIENT_SECTIONS):
        first = next(n for n in [m for i, m in enumerate(CLIENT_SECTIONS) if head[i:i + 1] != [m]] +
                     numbers[len(head):] if n != 16)
        return (WHOLE, "cannot find sections 1 to 15", "level-2 headings numbered 1 to 15, each once and in order, "
                "then section 16 (section %d is missing, repeated or out of order): %s" % (first, guide))
    started = False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if not heading or len(heading.group(1)) > 2:
            continue
        number = section_number(line)
        if number == 16:
            return None
        if number in CLIENT_SECTIONS:
            started = True
        elif started or len(heading.group(1)) == 2:
            return ("line %d" % (index + 1), "a level-%d heading that is not one of the sixteen numbered sections "
                    "sits before section 16, so the text under it would not be checked" % len(heading.group(1)),
                    "every item inside one of the sixteen sections as a level-3 subsection (### <item>), internal "
                    "notes under section 16: %s" % guide)
    return None


def marked_lines(lines, marks):
    """Every line from a mark to the next level-1 or level-2 heading, the mark lines included."""
    found, active = set(), False
    for index, line in enumerate(lines):
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            active = False
        if line.strip() in marks or near_mark(line) == "glossary":
            active = True
        if active:
            found.add(index)
    return found


def cmd_wall(run):
    """X08: the wall alone, on one planned name or text, against the index, the slugs and this record's O."""
    run.locate()
    check_unit(run, Unit("--text", run.args.text, (0, 0), mode="wall"))
    return outcome(run)


def client_identity(run):
    """(name, slug, former names) from CLIENT.md's front matter (R40); X30: the slug must be the folder's name."""
    meta = mc.front_matter(run.text(run.root / "CLIENT.md", "CLIENT.md"), "CLIENT.md")
    slug, name = (meta.get("slug") or "").strip(), (meta.get("name") or "").strip()
    if not slug or not words_of(slug):
        raise cannot("CLIENT.md", "slug", "the record has no slug", 'slug: "<the folder name>" in the front matter')
    if slug != run.root.name:
        raise cannot("CLIENT.md", "slug", "the slug %r is not the folder's name %r" % (slug, run.root.name),
                     "a record whose CLIENT.md slug is its folder name, so its index key matches its folder")
    return name, slug, mc.former_names(meta.get("former_names"))


def cmd_index(run):
    """X02, X29, X46: write this record's clients-index/1 entry under the home mutex, in place with a backup, and
    nothing at all when the four lists are unchanged and the entry is not older than the record's files (R44)."""
    run.locate()
    name, slug, former = client_identity(run)
    twin_folder(run)
    wall_stop(run)
    # G13, R44: the clock and the newest change are taken before any file is read, so a file written while the
    # entry is built is newer than the entry. The stamp is the later of the two, so an entry is never older than
    # the files it was built from, whatever the clock or a file's time says.
    begun, (failed, outside) = mc.now_utc(), record_failures(run)
    newest = newest_change(record_walk(run.root, failed, outside), failed)
    run.exclusions = load_exclusions(run)
    run.sets = build_sets(run)
    run.findings = []  # the record's own mark warnings belong to scan; index runs no rule
    lists, single = build_entry(run, name, slug, former)
    run.extra["single_words"] = {"count": len(single), "words": single}  # G16: this record's own, so shown
    key, path = mc.slug_key(slug), run.home / "clients-index.json"
    with mc.record_mutex(run.home):
        entries, old = read_index(run, locked=True)
        entry = entries.get(key)
        if entry is not None and not holds_own_name(entry, [name] + former) and entry_is_damaged(entry, slug):
            # G14, R45: an entry without the slug's name is no client's entry as index wrote it, so R35's name test
            # cannot tell; it is replaced only when this record's lists hold every digest it still holds
            if any(set(entry[field]) - set(lists[field]) for field in LIST_FIELDS):
                raise index_problem(INDEX_FIELDS[4], "the entry under this record's slug is damaged (it lacks the "
                                    "slug's name, which index always writes) and holds digests this record would "
                                    "not write, so replacing it could drop another client's wall", "restore the "
                                    "whole clients-index.json from its backup under <home>/local/backup/, then run "
                                    "index again")
        elif entry is not None and not holds_own_name(entry, [name] + former):
            # G07, X29, R40: an entry that holds neither this record's CLIENT.md name nor one of its former names is
            # another client's; never replaced
            raise index_problem(INDEX_FIELDS[4], "the entry under this record's slug belongs to another client "
                                "(it holds neither this record's CLIENT.md name nor any of its former names), and an "
                                "entry is never replaced by another client's", "one slug per client: give this record "
                                "another slug, or, if this client was renamed, keep its old name with record.py "
                                "client rename or in CLIENT.md's former_names, then run index again")
        if entry is None or any(entry[field] != lists[field] for field in LIST_FIELDS) or \
                entry_is_older(entry, newest):
            moment = max(begun, datetime.fromtimestamp(newest, timezone.utc))
            entry = dict([(INDEX_FIELDS[5], mc.stamp("utc", moment))] +
                         [(field, lists[field]) for field in LIST_FIELDS])
        entries[key] = entry
        text = index_text(entries)
        written = text != old
        if written:
            mc.write_file(path, text, run.home, backup_dir=run.home / "local" / "backup")
    run.extra["written"] = written
    return 0


def cmd_terms(run):
    """X31: every file under a folder, against every entry's digests, every folder's slug and the firm rule."""
    folder = Path(run.args.folder)
    if not folder.is_dir():
        raise cannot(run.args.folder.replace("\\", "/"), "folder", "not a folder", "a folder to check, such as the "
                     "plugin's shared/")
    run.root, run.home, run.record = folder.resolve(), mc.home(), False
    load_lists(run)
    wall_hits(run, None)
    run.extra.update(entries_compared=run.wall.entries, slugs_compared=run.wall.folders)

    def failed(exc):
        raise cannot(exc.filename or run.args.folder, WHOLE, "cannot list the folder: %s" % exc, "a readable folder")

    def outside(path, folder):  # R38: a release bundle follows links, so one that leaves the folder is a stop
        raise cannot(Path(os.path.relpath(path, str(run.root))).as_posix(), WHOLE, "a linked %s resolves outside "
                     "the folder checked" % ("folder" if folder else "file"), "files inside the folder only; copy "
                     "them in or remove the link, then run this again")

    found = walk_files(run.root, run.root, failed, outside, lambda parts: parts[-1:] in TERMS_SKIP_PARTS)
    for seq, rel in enumerate(sorted(found)):
        path = found[rel]
        ext = os.path.splitext(rel)[1].lower()
        if ext == ".docx":
            for index, (part, lines, labels) in enumerate(docx_text(run, path, rel)):
                check_unit(run, Unit(rel, "\n".join(lines), (seq, index), part=part, mode="terms", labels=labels))
            continue
        data = run.read(path, rel)
        if ext not in TERMS_EXT and data:  # Z14: an empty file holds nothing to prove, whatever its name
            raise cannot(rel, WHOLE, "the lint cannot read this kind of file", "a text file (%s) or a .docx; move "
                         "this one out of the folder" % ", ".join(TERMS_EXT))
        text, raw = decode(data, rel)
        check_unit(run, Unit(rel, text, (seq, 0), mode="terms", raw=raw))
    return outcome(run)


COMMANDS = {"scan": cmd_scan, "payload": cmd_payload, "blueprint": cmd_blueprint, "wall": cmd_wall,
            "terms": cmd_terms, "index": cmd_index}
EXIT_VERDICT = {0: VERDICTS[0], 1: VERDICTS[2], 2: VERDICTS[1], 3: VERDICTS[3]}


def outcome(run):
    severities = {f["severity"] for f in run.findings}
    return 1 if "block" in severities else (2 if severities else 0)


def envelope(run, code):
    data = {"ok": code in (0, 2), "command": run.command, "verdict": EXIT_VERDICT[code]}
    if run.command in ("scan", "blueprint"):
        data["mode"] = run.mode
    data["strand"] = run.strand
    data["inputs"] = [run.inputs[name] for name in sorted(run.inputs)]
    if run.command == "payload":
        data["args_digest"] = run.args_digest
    data.update(run.extra)
    findings = sorted(run.findings, key=lambda f: f["_order"])
    data["findings"] = [{k: v for k, v in f.items() if not k.startswith("_")} for f in findings]
    data["counts"] = {severity: sum(1 for f in findings if f["severity"] == severity) for severity in SEVERITIES}
    if code == 3:
        data["error"] = run.error
    return data


def full_error(found):
    """Every part of the error non-empty (L27)."""
    defaults = {"file": "leak_lint.py", "field": WHOLE, "problem": "the lint could not run", "expected": "a run that "
                "finishes"}
    return {key: (str(found.get(key)) if found.get(key) not in (None, "") else defaults[key]) for key in KEYS}


def build_parser():
    parser = Parser(prog="leak_lint.py", description="The leak lint.", add_help=False)
    parser.add_argument("--record", help="the client folder (default: the current folder)")
    top = parser.add_subparsers(dest="command", metavar="command", parser_class=Parser)
    top.required = True
    scan = top.add_parser("scan", add_help=False)
    scan.add_argument("--strand")
    scan.add_argument("--spans", action="store_true")
    scan.add_argument("paths", nargs="*")
    payload = top.add_parser("payload", add_help=False)
    payload.add_argument("--strand", required=True)
    payload.add_argument("--kind", required=True, choices=KINDS)
    payload.add_argument("--file", required=True)
    payload.add_argument("--spans", action="store_true")
    blueprint = top.add_parser("blueprint", add_help=False)
    blueprint.add_argument("--strand", required=True)
    blueprint.add_argument("--spans", action="store_true")
    wall = top.add_parser("wall", add_help=False)
    wall.add_argument("--text", required=True)
    terms = top.add_parser("terms", add_help=False)
    terms.add_argument("folder")
    top.add_parser("index", add_help=False)
    return parser


def run_command(argv=None):
    """(exit code, the envelope) of one command, printing nothing: main() prints it, and record.py calls it in
    process for `index` after its own writes, so its output stays one envelope (R48)."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except Usage as exc:
        return 3, {"ok": False, "command": None, "verdict": VERDICTS[3], "inputs": [], "findings": [],
                   "counts": {severity: 0 for severity in SEVERITIES},
                   "error": dict(zip(KEYS, ("leak_lint.py", "arguments", str(exc), parser.format_usage().strip())))}
    run = Run(args.command, args)
    try:
        handler = COMMANDS[args.command]
        code = handler(run)
    except mc.MMBError as exc:  # a refusal of mmb_common is still "could not run" here: exit 1 means a leak only
        run.error, code = full_error(exc.findings[0] if exc.findings else {}), 3
    except Exception as exc:  # G10, L205: anything unexpected is "could not run", still one JSON object
        run.error, code = full_error({"file": "leak_lint.py", "field": type(exc).__name__, "problem": str(exc) or
                                      "an internal error with no message", "expected": "a run without an internal "
                                      "error"}), 3
    return code, envelope(run, code)


def main(argv=None):
    code, data = run_command(argv)
    emit(data)
    return code


if __name__ == "__main__":
    sys.exit(main())
